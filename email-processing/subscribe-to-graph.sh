#!/bin/bash
source terraform/.env

export TENANT_ID=$TF_VAR_graph_tenant_id
export CLIENT_ID=$TF_VAR_graph_client_id
export CLIENT_SECRET=$TF_VAR_graph_client_secret


#get current time
export CURRENT_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
# add 10070 minutes to the current time
export EXPIRATION_TIME=$(date -u -d "$CURRENT_TIME + 10070 minutes" +"%Y-%m-%dT%H:%M:%SZ")


# Get the access token
TOKEN=$(curl -s -X POST \
  "https://login.microsoftonline.com/$TENANT_ID/oauth2/v2.0/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "client_id=$CLIENT_ID" \
  -d "client_secret=$CLIENT_SECRET" \
  -d "scope=https://graph.microsoft.com/.default" \
  -d "grant_type=client_credentials" | jq -r '.access_token')

# Check if the token was retrieved successfully
if [ -z "$TOKEN" ]; then
  echo "Failed to retrieve access token"
  exit 1
fi
# Subscribe to the Microsoft Graph API


export PAYLOAD='{"changeType": "created","notificationUrl": "'$NOTIFICATION_URL'","resource": "/users/'$EMAIL'/messages","expirationDateTime": "'$EXPIRATION_TIME'","clientState": "secretClientValue"}'

echo $PAYLOAD | jq .

curl -vvv -X POST \
  "https://graph.microsoft.com/v1.0/subscriptions" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD" | jq .
