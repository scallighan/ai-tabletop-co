from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
import logging
from logging.config import dictConfig
from .log_config import log_config
import json
import os
import base64
import pyodbc

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

from azure.ai.contentunderstanding.models._models import ObjectField
dictConfig(log_config)
logger = logging.getLogger("api-logger")

app = FastAPI(
    title="Graph Tagger Agent",
)

SQL_SERVER_NAME = os.environ.get("SERVER_NAME")
SQL_DATABASE_NAME = os.environ.get("DATABASE_NAME")

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
    try:
        field = fields.get(field_name)
        # log the type of the field and its value
        logger.info(f"Extracting field '{field_name}': type={type(field)}, value={field.value if field else None}")
        # if the field is azure.ai.contentunderstanding.models._models.ObjectField, we need to access the Amount field to get the actual object
        if isinstance(field, ObjectField):
            logger.info(f"Field '{field_name}' is an ObjectField, attempting to extract 'Amount' field from it")
            amount_field = field.value_object.get("Amount")
            if amount_field:
                logger.info(f"Extracting Amount from ObjectField '{field_name}': type={type(amount_field)}, value={amount_field.value if amount_field else None}")
                return amount_field.value if amount_field else field.value
        return field.value if field else None
    except Exception as e:
        logger.error(f"Error extracting field '{field_name}': {str(e)}")
        return None

async def process_attachment(attachment, email_id):
    credential = DefaultAzureCredential()
    client = ContentUnderstandingClient(endpoint=os.environ.get("CONTENTUNDERSTANDING_ENDPOINT"), credential=credential)
    logger.info(f"Attachment name: {attachment.name}, content_type: {attachment.content_type}, size: {attachment.size}")
    # Get the binary content of the attachment
    content_bytes_base64 = attachment.content_bytes
    
    if content_bytes_base64:
        logger.info(f"Attachment '{attachment.name}' binary content size: {len(content_bytes_base64)} bytes")
        if attachment.content_type == "application/pdf":
            logger.info(f"Attachment '{attachment.name}' is a PDF, proceeding with analysis")
            try:
                content_bytes = base64.b64decode(content_bytes_base64) if content_bytes_base64 else None
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
                    lineitems = await get_field_value(document_content.fields, "LineItems")
                    pONumber = await get_field_value(document_content.fields, "PONumber")
                    customerName = await get_field_value(document_content.fields, "CustomerName")
                    subtotalAmount = await get_field_value(document_content.fields, "SubtotalAmount")
                    totalTaxAmount = await get_field_value(document_content.fields, "TotalTaxAmount")
                    totalAmount = await get_field_value(document_content.fields, "TotalAmount")
                    rows = []
                    if lineitems:
                        row = ["PONumber", "CustomerName", "Description", "ProductCode", "Quantity", "QuantityUnit", "UnitPrice", "TaxAmount", "TaxRate", "LineTotal", "SubtotalAmount", "TotalTaxAmount", "TotalAmount"]
                        rows.append(row)
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
                                line_total = await get_field_value(item_obj, "TotalAmount")
                                logger.info(f"LineItem {idx}: Description={description}, ProductCode={product_code}, Quantity={quantity} {quantity_unit}, UnitPrice={unit_price}, TaxAmount={tax_amount}, TaxRate={tax_rate}, LineTotal={line_total}")
                                row = [f"{pONumber}", f"{customerName}", f"{description}", f"{product_code}", f"{quantity}", f"{quantity_unit}", f"{unit_price}", f"{tax_amount}", f"{tax_rate}", f"{line_total}", f"{subtotalAmount}", f"{totalTaxAmount}", f"{totalAmount}"]
                                rows.append(row)

            except Exception as e:
                logger.error(f"Error while processing analysis result: {str(e)}")   
            # write out the markdown content to a blob storage container for later review
            blob_service_client = BlobServiceClient(credential=credential, account_url=f"https://{os.environ.get('STORAGE_ACCOUNT_NAME')}.blob.core.windows.net")
            container_client = blob_service_client.get_container_client(os.environ.get('STORAGE_CONTAINER_NAME'))
            blob_name = f"{email_id}/{attachment.name}.md"
            blob_client = container_client.get_blob_client(blob_name)
            markdown_content = content.markdown
            blob_client.upload_blob(markdown_content, overwrite=True)
            logger.info(f"Uploaded analysis result for attachment '{attachment.name}' to blob storage as '{blob_name}'")
            if len(rows) > 1:
                logger.info(f"Rows to insert into SQL: {len(rows) - 1}")
                try:
                    token = credential.get_token("https://database.windows.net/.default")
                    conn = pyodbc.connect(
                        f"Driver={{ODBC Driver 18 for SQL Server}};"
                        f"Server=tcp:{SQL_SERVER_NAME}.database.windows.net,1433;"
                        f"Database={SQL_DATABASE_NAME};"
                        f"UID={os.environ.get('AZURE_CLIENT_ID')};"
                        "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;Authentication=ActiveDirectoryMsi;"
                    )
                    cursor = conn.cursor()
                    insert_sql = (
                        "INSERT INTO PurchaseOrderLines "
                        "(PONumber, CustomerName, Description, ProductCode, Quantity, QuantityUnit, "
                        "UnitPrice, TaxAmount, TaxRate, LineTotal, SubtotalAmount, TotalTaxAmount, TotalAmount) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                    )
                    for row in rows[1:]:  # skip header row
                        params = [None if v == "None" else v for v in row]
                        cursor.execute(insert_sql, params)
                    conn.commit()
                    cursor.close()
                    conn.close()
                    logger.info(f"Inserted {len(rows) - 1} rows into PurchaseOrderLines table")
                except Exception as e:
                    logger.error(f"Error inserting rows into SQL: {str(e)}")
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
        if message.categories and ("ProcessingEmailAgent" in message.categories or "ProcessedEmailAgent" in message.categories):
            logger.info(f"Message {message_id} has already been processed, skipping")
            continue
        # Add the tagged category to the message
        update_message = Message(
            categories=["ProcessingEmailAgent"]
        )
        await client.users.by_user_id(user_id).messages.by_message_id(message_id).patch(update_message)
        body_content = message.body.content
        logger.info(f"Message: {body_content}")
        logger.info(f"Message subject: {message.subject}")
        logger.info(f"Message conversation_id: {message.conversation_id}")
        logger.info(f"Message conversation_index: {message.conversation_index}")

        # Get attachments if the message has any
        
        if message.has_attachments:
            attachments = await client.users.by_user_id(user_id).messages.by_message_id(message_id).attachments.get()
            for attachment in attachments.value:
                await process_attachment(attachment, message_id)
                    

        # Add the tagged category to the message
        update_message = Message(
            categories=["ProcessedEmailAgent"]
        )
        await client.users.by_user_id(user_id).messages.by_message_id(message_id).patch(update_message)



    return {"status": "success", "message": "Notification received"}
