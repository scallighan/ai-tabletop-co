# start_server.py
from os import environ
from microsoft_agents.hosting.core import AgentApplication, AgentAuthConfiguration
from microsoft_agents.hosting.aiohttp import (
   start_agent_process,
   jwt_authorization_middleware,
   CloudAdapter,
)
from aiohttp.web import Request, Response, Application, run_app, middleware, json_response

@middleware
async def headers_middlware(request: Request, handler):
   headers = request.headers
   print(f"Received request with headers: {headers}")
   auth_config: AgentAuthConfiguration = request.app["agent_configuration"]
   print(f"Using auth configuration: {auth_config}")
   return await handler(request)

def start_server(
   agent_application: AgentApplication, auth_configuration: AgentAuthConfiguration
):
   async def entry_point(req: Request) -> Response:
      agent: AgentApplication = req.app["agent_app"]
      adapter: CloudAdapter = req.app["adapter"]
      return await start_agent_process(
            req,
            agent,
            adapter,
      )

   APP = Application(middlewares=[headers_middlware, jwt_authorization_middleware])
   APP.router.add_post("/api/messages", entry_point)
   APP.router.add_get("/api/messages", lambda _: Response(status=200))
   APP["agent_configuration"] = auth_configuration
   APP["agent_app"] = agent_application
   APP["adapter"] = agent_application.adapter

   try:
      run_app(APP, host="0.0.0.0", port=environ.get("PORT", 3978))
   except Exception as error:
      raise error