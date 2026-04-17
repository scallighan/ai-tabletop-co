from microsoft_agents.activity import load_configuration_from_env
from microsoft_agents.authentication.msal import MsalConnectionManager
from microsoft_agents.hosting.core import (
   AgentApplication,
   Authorization,
   TurnState,
   TurnContext,
   MemoryStorage,
)
from microsoft_agents.hosting.aiohttp import CloudAdapter
from os import environ
from .server import start_server
import os
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from openai.types.responses.response_input_param import McpApprovalResponse, ResponseInputParam

agents_sdk_config = load_configuration_from_env(environ)
print(f"Loaded configuration: {agents_sdk_config}")
# Create storage and connection manager
STORAGE = MemoryStorage()
CONNECTION_MANAGER = MsalConnectionManager(**agents_sdk_config)
ADAPTER = CloudAdapter(connection_manager=CONNECTION_MANAGER)
AUTHORIZATION = Authorization(STORAGE, CONNECTION_MANAGER, **agents_sdk_config)

AGENT_APP = AgentApplication[TurnState](
    storage=STORAGE,
    adapter=ADAPTER,
    authorization=AUTHORIZATION
)

CONVERSATION_ID=None

async def _help(context: TurnContext, _: TurnState):
    await context.send_activity(
        "Welcome to the Level Up Agent sample 🚀. "
        "Type 'help' for help or send a message to see the echo feature in action."
    )

async def _reset(context: TurnContext, _: TurnState):
    global CONVERSATION_ID
    CONVERSATION_ID = None
    await context.send_activity("Conversation reset. Start a new conversation to see the effect.")

#AGENT_APP.conversation_update("membersAdded")(_help)

AGENT_APP.message("help")(_help)
AGENT_APP.message("reset")(_reset)

async def handle_responses(agent_name, openai_client, response):
    global CONVERSATION_ID
    print("Handling response...")
    input_list: ResponseInputParam = []
    for item in response.output:
        if item.type == "mcp_approval_request":
            input_list.append(
                McpApprovalResponse(
                    type="mcp_approval_response",
                    approve=True,
                    approval_request_id=item.id,
                )
            )

    print("Final input:")
    print(input_list)
    if len(input_list) > 0:
        response = openai_client.responses.create(
            input=input_list,
            conversation=CONVERSATION_ID,
            extra_body={"agent_reference": {"name": agent_name, "type": "agent_reference"}},
        )
        return await handle_responses(agent_name, openai_client, response)
    else:
        print(f"Returning output text: {response.output_text}")
        return response.output_text
    
@AGENT_APP.activity("message")
async def on_message(context: TurnContext, _):
    global CONVERSATION_ID

    text = context.activity.text
    print(f"Received message: {text}")
    try:
        credential = DefaultAzureCredential()
        project_client = AIProjectClient(credential=credential, endpoint=os.getenv("AZURE_AI_PROJECT_ENDPOINT"))
        with project_client.get_openai_client() as openai_client:
            agent_name = "AnalyticsInsightsAgent"
            if CONVERSATION_ID is None:
                conversation = openai_client.conversations.create()
                CONVERSATION_ID = conversation.id
            print(f"Using conversation ID: {CONVERSATION_ID}")
            response = openai_client.responses.create(
                tool_choice="required",
                conversation=CONVERSATION_ID,
                input=text,
                extra_body={"agent_reference": {"name": agent_name, "type": "agent_reference"}},
            )
            output_text = await handle_responses(agent_name, openai_client, response)
            await context.send_activity(f"{output_text}")
    except Exception as e:
        print(f"Error processing message: {e}")
        await context.send_activity(f"Sorry, something went wrong while processing your message. {e}")


    
    

if __name__ == "__main__":
    try:
        start_server(AGENT_APP, CONNECTION_MANAGER.get_default_connection_configuration())
    except Exception as error:
        raise error