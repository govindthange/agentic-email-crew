# Phase 2: Microservices Architecture

> This section contains all the prompts for phase 2 of the project. LLM should not process this file.

> The tasks listed in this section are to be processed by LLM model one at a time, as and when, each task is fed to the LLM model and awaited for completion. Upon completing one task, the next task should be fed to the LLM model by the user.

The microservices architecture will have following components:
1. react shell,
2. email-reader-service,
3. email-reader-ui (a microfrontend for email-reader-service).

All the components should be containerized and listed in docker-compose.yml file.

## Task 1: Refactor Email Reader Console [COMPLETED]

Bundle this python app we built so far as email-reader-console and move it in email-reader-console folder. This bundle will become a place holder microservice to be used for reference later for building email-reader-service. Nothing needs to change inside fetch_email.py code. Only move ./data/*, ./logs/*, .env, .env.example, .gitignore, README.md, requirements.txt, fetch_email.py to a folder named email-reader-console folder and treat it as a separate container to be instantiated inside docker compose file. Since this workspace is in git, When you do this refactoring like move these files use git move command.

## Task 2: Create a microservice as `Email Reader Service` [COMPLETED]

Now restructure this workspace into a microservices styled architecture workspace. 

Use email-reader-console's fetch_email.py code to create a new `email-reader-service` inside a new email-reader-service folder. The refactored version of fetch_email.py will become a microservice that implements multiple REST APIs like /api/email/fetch/last, /api/email/fetch/all, /api/email/read-count, /api/email/unread-count, /api/email/archive-count. docker-compose.yml should be updated to include this new service.

## Task 3: Create a microfrontend as `Email Reader UI` [COMPLETED]

Create a new `email-reader-ui` microfrontend using react. Each microservice, in this case `email-reader-service`, will be accompanied by its own microfrontend using react. The new `email-reader-ui` microfrontend will have several buttons, each to invoke its respective HTTP GET Method.

**For example:** `email-reader-ui` will have a simple button by the name "Fetch Last Email". Clicking on this button will invoke `/api/email/fetch/last` API. The HTTP GET method implemented inside `email-reader-service` microservice will return the last email fetched. The code should use logic inside fetch_email.py file to fetch the last email, save it in the ./data/archive-YYYYMMDD.json file, and return the last email fetched in JSON format. The JSON data will be shown in the microfrontend.

Similarly, there will be another button called "Get Today's Email Archive Count". When user clicks on this button it will simply invoke `/api/email/archive-count` API. The HTTP GET method implemented inside `email-reader-service` microservice will then return the size of the array inside ./data/archive-YYYYMMDD.json file for the current day.

Likewise, implement other buttons in `email-reader-ui` microfrontend and make them call their respective microservice's HTTP GET methods.

docker-compose.yml should be updated to include `email-reader-ui` service.

#### Concept

Each microfrontend ships as a JS bundle that registers a custom element, say <email-reader-ui-root>. The shell just imports that JS and drops the tag into its React tree.

#### How it works?

email-reader-ui builds to a bundle that does customElements.define('email-reader-ui-root', class extends HTMLElement { /* mounts React */ }).
react-shell HTML (or React) does <email-reader-ui-root backend-origin="/api/email" />.

**Pros:** Framework-agnostic, standard browser feature, natural for cross-team boundaries.
**Cons:** More plumbing to bridge React ↔ web components; still needs a build pipeline.

> Relationship between react-shell and email-reader-ui should be such that when they are shown on any browser the react-shell component displays `email-reader-ui` and other microfrontends inside it (but not inside any iframe or as a separate tab). Implement how microfrontends are composed in a typical microservices styled architecture.

In the end add a README.md file to `email-reader-ui` microfrontend which will describe how to use and test this microfrontend.

## Task 4: React Shell [COMPLETED]

Introduce the idea of react shell (a `react-shell` microservice) so that we do not have a single RIA controlling front ends of all the microservices and becomes a bottleneck.

> Note that we do not want react-shell to be implemented as a div containing some iframe or altogether a separate tab. There are several non-iframe patterns for a React shell to federate UIs from multiple microfrontends of different microservices. In practice, most modern microfrontend setups use  Web Components (custom elements) as the integration contract

 The react-shell should import and use the custom elements of the microfrontends. Essentially, react-shell will be mainly used to open on browser and view all microfrontends federated by the react-shell.
