# ai-tabletop-co
AI Demo for a fictitious board game manufacturing company

## About the Fictitious Company
AI Tabletop Co. is a mid-sized board game manufacturer and publisher specializing in premium strategy, euro-style, and narrative-driven tabletop games. The company designs, manufactures, and distributes games globally, with a strong emphasis on component quality, sustainability, and scalable production.

## About the Demo
AI Tabletop Co. needs to take various order forms and contracts that come in via email and put them into a unified data platform (Fabric)

Then backend processors need to validate that they can meet demands and get insights on their sales data.

## Setup

### Infrastructure
```
cd terraform
cp env.sample .env
```

Populate the values for .env

Run terraform

```
source .env
terraform apply
```

### Subscribe to emails
Navigate to `email-processing`
```
cp env.sample .env
```

Populate the values in .env

```
./subscribe-to-graph.sh
```

### Foundry
Deploy the following models
* model-router
* gpt-4.1
* gpt-4.1-mini
* text-embedding-3-large


