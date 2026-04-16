from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
import logging
from logging.config import dictConfig
from .log_config import log_config
import json
import os
import base64

from azure.identity.aio import ClientSecretCredential

from msgraph import GraphServiceClient
from msgraph.generated.models.message import Message

from azure.identity import DefaultAzureCredential
from azure.ai.contentunderstanding import ContentUnderstandingClient
from azure.ai.contentunderstanding.models import (
    AnalysisContent,
    AnalysisContentKind,
    AnalysisResult,
    DocumentContent
)
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient


dictConfig(log_config)
logger = logging.getLogger("api-logger")

app = FastAPI(
    title="Graph Tagger Agent",
)

@app.middleware('http')
async def logging_middleware(request: Request, call_next):
    logger.info("logging_middleware")
    # Log method, url, headers, query params, path params, and scope
    logger.info(f"Request method: {request.method}")
    logger.info(f"Request url: {request.url}")
    logger.info(f"Request headers: {dict(request.headers)}")
    logger.info(f"Request query_params: {dict(request.query_params)}")
    logger.info(f"Request path_params: {request.path_params}")
    logger.info(f"Request client: {request.client}")
    logger.info(f"Request cookies: {request.cookies}")
    logger.info(f"Request scope: {json.dumps({k: str(v) for k, v in request.scope.items()})}")
    # Optionally, log the body (if needed and safe)
    body = await request.body()
    logger.info(f"Request body: {body}")
    response = await call_next(request)
    return response

@app.get("/")
async def read_root():
    return {"Hello": "World"}

async def get_field_value(fields, field_name):
    """Helper function to safely extract field values."""
    field = fields.get(field_name)
    return field.value if field else None

async def process_attachment(attachment):
    credential = DefaultAzureCredential()
    client = ContentUnderstandingClient(endpoint=os.environ.get("CONTENTUNDERSTANDING_ENDPOINT"), credential=credential)
    logger.info(f"Attachment name: {attachment.name}, content_type: {attachment.content_type}, size: {attachment.size}")
    # Get the binary content of the attachment
    content_bytes = attachment.content_bytes
    if content_bytes:
        logger.info(f"Attachment '{attachment.name}' binary content size: {len(content_bytes)} bytes")
        if attachment.content_type == "application/pdf":
            logger.info(f"Attachment '{attachment.name}' is a PDF, proceeding with analysis")
        
            poller = client.begin_analyze_binary(
                analyzer_id="prebuilt-procurement",
                binary_input=content_bytes,
            )
            result: AnalysisResult = poller.result()
            if not result.contents or len(result.contents) == 0:
                logger.warning("No content found in the analysis result.")
                return
            content: AnalysisContent = result.contents[0]

            # Access document-specific properties
            if content.kind == AnalysisContentKind.DOCUMENT:
                document_content: DocumentContent = content  # type: ignore
                lineitems = await get_field_value(content.fields, "LineItems")
                if lineitems:
                    logger.info(f"Extracted LineItems: {len(lineitems)}")
                    for idx, item in enumerate(lineitems):
                        if hasattr(item, 'value_object') and item.value_object:
                            item_obj = item.value_object
                            description = await get_field_value(item_obj, "Description")
                            product_code = await get_field_value(item_obj, "ProductCode")
                            quantity = await get_field_value(item_obj, "Quantity")
                            quantity_unit = await get_field_value(item_obj, "QuantityUnit")
                            tax_amount = await get_field_value(item_obj, "TaxAmount")
                            tax_rate = await get_field_value(item_obj, "TaxRate")
                            unit_price = await get_field_value(item_obj, "UnitPrice")
                            logger.info(f"LineItem {idx}: Description={description}, ProductCode={product_code}, Quantity={quantity} {quantity_unit}, UnitPrice={unit_price}, TaxAmount={tax_amount}, TaxRate={tax_rate}")
            
            # write out the markdown content to a blob storage container for later review
            blob_service_client = BlobServiceClient(credential=credential, account_url=f"https://{os.environ.get('STORAGE_ACCOUNT_NAME')}.blob.core.windows.net")
            container_client = blob_service_client.get_container_client(os.environ.get('STORAGE_CONTAINER_NAME'))
            blob_name = f"{attachment.name}_{attachment.id}.md"
            blob_client = container_client.get_blob_client(blob_name)
            markdown_content = content.markdown
            blob_client.upload_blob(markdown_content, overwrite=True)
            logger.info(f"Uploaded analysis result for attachment '{attachment.name}' to blob storage as '{blob_name}'")
            return
        else:
            logger.warning(f"Attachment '{attachment.name}' is not a PDF (content_type: {attachment.content_type}), skipping analysis")
            return
                            

    

@app.post("/notifications")
async def notifications(request: Request):
    # Log the request body
    body = await request.body()
    logger.info(f"Received notification body: {body}")
    logger.info(f"Received notification query_params: {dict(request.query_params)}")
    if "validationToken" in dict(request.query_params):
        logger.info(f"Received validation token: {request.query_params['validationToken']}")
        return PlainTextResponse(request.query_params["validationToken"])
    
    # Process the notification (this is just a placeholder)
    # You can add your processing logic here

    body_json = json.loads(body)
    credentials = ClientSecretCredential(
        os.environ.get('GRAPH_TENANT_ID'),
        os.environ.get('GRAPH_CLIENT_ID'),
        os.environ.get('GRAPH_CLIENT_SECRET'),
    )
    scopes = ['https://graph.microsoft.com/.default']
    client = GraphServiceClient(credentials=credentials, scopes=scopes)

    for notification in body_json['value']:
        # Process each notification
        logger.info(f"Processing notification: {notification}")
        # Example: Get the resource URL from the notification
        resource_url = notification['resource']
        logger.info(f"Resource URL: {resource_url}")
        resource_parts = resource_url.split('/')
        user_id = resource_parts[1]
        message_id = resource_parts[3]

        # Get the message ID from the notification
        message = await client.users.by_user_id(user_id).messages.by_message_id(message_id).get()
        # check the categories of the message to see if it has already been processed
        logger.info(f"Message categories: {message.categories}")
        if message.categories and "EmailProcessingAgentProcessed" in message.categories:
            logger.info(f"Message {message_id} has already been processed, skipping")
            continue

        body_content = message.body.content
        logger.info(f"Message: {body_content}")
        logger.info(f"Message subject: {message.subject}")
        logger.info(f"Message conversation_id: {message.conversation_id}")
        logger.info(f"Message conversation_index: {message.conversation_index}")

        # Get attachments if the message has any
        
        if message.has_attachments:
            attachments = await client.users.by_user_id(user_id).messages.by_message_id(message_id).attachments.get()
            for attachment in attachments.value:
                await process_attachment(attachment)
                    

        # Add the tagged category to the message
        update_message = Message(
            categories=["EmailProcessingAgentProcessed"]
        )
        await client.users.by_user_id(user_id).messages.by_message_id(message_id).patch(update_message)



    return {"status": "success", "message": "Notification received"}
