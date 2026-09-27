# TIB-AV-A

<!-- ![](images/iart-salvator.png) -->


## Overview

<!-- The project iART is devoted to the development of an e-Research-tool for digitized, image-oriented research processes in the humanities and cultural sciences. It not only aims to improve the efficiency of retrieval in image databases but also offers various tools for analyzing image data, thereby enhancing scientific work and facilitating new theory formation. The motivation for the project stems from the fundamental importance of the comparative approach in art history, which targets the similarity of pictures and comes along with a rehabilitation of similarity thinking in contemporary philosophy of science. iART is supposed to transfer the approach of art history theorists and practitioners of Comparative Analysis to the digital age, and to extend it by virtue of modern information technology.  -->


## Installation

<!-- At a later point there will be a docker container provided here. -->


## Development setup


### Requirements
* [docker](https://docs.docker.com/get-docker/)
* [docker-compose](https://docs.docker.com/compose/install/)


### Setup process
1. Clone the TIB-AV-A repository including submodules:
    ```sh
    git clone https://github.com/TIBHannover/tibava.git
    cd tibava
    ```

2. Download and extract models:
    ```sh
    mkdir data/cache
    mkdir data/analyser
    mkdir data/media
    mkdir data/tmp
    mkdir data/predictions
    mkdir data/backend_cache
    wget https://tib.eu/cloud/s/kAe3TXPfsBpwtwk/download/models.tar.gz
    tar -xf models.tar.gz --directory data/
    ```

3. Build and start the container:
    ```sh
    sudo docker-compose up --build
    ```

4. Apply database migrations and build frontend packages:
    ```sh
    sudo docker-compose exec backend python3 backend/src/backend/manage.py migrate auth
    sudo docker-compose exec backend python3 backend/src/backend/manage.py migrate
    sudo docker-compose exec frontend npm install
    sudo docker-compose exec frontend npm run build
    ```
    > The `npm install`/`npm run build` lines apply if the frontend is built from `frontend/Dockerfile` (the npm-enabled nginx image). With the default root `docker-compose.yml` + `Dockerfile.frontend` (multi-stage) build, `npm install`/`npm run build` already run at image-build time and the resulting container has no npm, so these two lines will fail with `exec: "npm": executable file not found in $PATH` — skip them in that case.

5. Go to the frontend instance at `http://localhost/`.


### Code reloading
Hot reloading is enabled for `backend`. To display frontend changes, run:
```sh
sudo docker-compose exec frontend npm run build
```
Alternatively, use `serve` to enable a hot reloaded instance on `http://localhost:8080/`:
```sh
sudo docker-compose exec frontend npm run serve
```
> These `npm run build`/`npm run serve` exec commands require the npm-enabled frontend container (built from `frontend/Dockerfile`). With the default `Dockerfile.frontend` image there is no npm inside the container, so instead pick up frontend changes by rebuilding that service:
> ```sh
> sudo docker-compose up --build frontend
> ```

### Geolocation LLM configuration
The `geolocation` backend plugin calls an external LLM to guess where a shot was filmed. Whether it uses a mock response or a live call depends on `DEBUG`:

* **`DEBUG=true`** — the plugin uses an in-process mock (`MockGeolocationLLMClient` in `backend/src/backend/backend/utils/llm_client.py`) that returns randomized sample locations. No API key, URL, or network access is required.
* **`DEBUG=false`** — the plugin calls a real LLM over HTTP, using a chat-completions-style request (`{"model", "messages", "stream": false}`, matching an OpenAI-compatible gateway such as the Dartmouth chat API). This requires three settings:
  * `GEOLOCATION_LLM_API_KEY` — API key for the external LLM.
  * `GEOLOCATION_LLM_API_URL` — endpoint to send requests to.
  * `GEOLOCATION_LLM_API_MODEL` — model name to request.
  * `GEOLOCATION_LLM_TIMEOUT_SECONDS` — per-attempt HTTP read timeout in seconds (default `120`). Live vision-model calls with several images can take well over a minute; raise this if requests are timing out under load.

Set them either in `backend/src/backend/.env` (picked up automatically) or under a `[geolocation]` section in `backend/src/backend/backend_config.toml`, the same way the analyser service's `[analyser]` section configures `grpc_host`/`grpc_port`:
```toml
[geolocation]
api_url = "https://example.com/geolocate"
api_key = "sk-..."
api_model = "some-model-name"
timeout_seconds = 120
```
Video frames are attached to the request as `image_url` content parts alongside the text prompt — this multimodal shape has been confirmed working against the live Dartmouth chat endpoint. Without all three required settings, the plugin fails immediately with a clear error instead of running.

The plugin itself runs asynchronously via Celery (dispatched from the `backend` web process but executed in the `celery` container), so a live call's request/response detail won't appear in `backend`'s logs — watch `docker-compose logs -f celery` instead. `GeolocationLLMClient` logs each attempt at `INFO` level: the outgoing URL/model/headers (secrets masked)/payload (base64 image data collapsed to a length+hash), and the raw response status/body, each line labeled with the shot it belongs to (`shot=<id>`) so a multi-shot run's logs stay traceable.

### Testing LLM/API-based plugins without a real endpoint
`backend/src/backend/backend/views/llm_test_echo.py` is a small dev-only endpoint, routed at `llm/test-echo/<plugin_name>/`, for smoke-testing a plugin's outbound API call without a real external service. It only responds when `DEBUG=true` (404s otherwise), so it's safe to leave in the codebase rather than delete after each use. It's a general-purpose manual inspection tool for any LLM/API-based plugin — the `geolocation` plugin itself no longer needs it for its own DEBUG-mode mock (see above), since that's now handled in-process.

To use it for a plugin, point that plugin's API-URL setting at it and make sure `backend` is an allowed host, e.g. in `backend/src/backend/.env`:
```
DEBUG=true
ALLOWED_HOSTS=localhost,backend
SOME_OTHER_PLUGIN_API_URL=http://backend:8000/llm/test-echo/some_other_plugin/
SOME_OTHER_PLUGIN_API_KEY=test-key
```
`http://backend:8000` (not `localhost`) is required because these calls originate from the `celery` container, addressing `backend` by its docker-compose service name; without `ALLOWED_HOSTS` including `backend`, Django rejects the request with `DisallowedHost`.

Watch what it receives with:
```sh
docker-compose logs -f backend celery
```
Each request is logged with any secret-looking headers (`Authorization`, or a name containing `key`/`token`/`secret`) masked, and any string over ~300 chars (e.g. a base64-encoded image) summarized as a length + `sha256` digest + short prefix instead of dumped in full — the hash makes it possible to tell identical vs. distinct payloads apart (e.g. to catch accidentally duplicated frames) without a raw, unreadable log line.

It responds with a fixed JSON body from the `FIXTURES` dict in that file, keyed by `plugin_name` (a `"geolocation"` entry is included, sourced from the same mock used by `MockGeolocationLLMClient`; unregistered plugin names get `[]`). To exercise a new plugin's response-parsing/DB-write code end-to-end rather than just its outbound request, add a fixture entry there shaped like what that plugin's client expects.

> **Geolocation demo note:** This repository is a modified demo based on
> [TIB AV-Analytics](https://github.com/TIBHannover/tibava). It adds a mock
> geolocation map and shot timeline for UI demonstration only; no
> geolocation model output is used. This modified work remains licensed under
> the GPL-3.0; see [LICENSE](LICENSE).

<!-- ## About the project

iART was funded by the [DFG](https://gepris.dfg.de/gepris/projekt/415796915) from 2019 to 2021. Our team consists of [Matthias Springstein](https://www.tib.eu/de/forschung-entwicklung/visual-analytics/mitarbeiterinnen-und-mitarbeiter/matthias-springstein/), [Stefanie Schneider](https://www.kunstgeschichte.uni-muenchen.de/personen/wiss_ma/schneider/index.html), [Javad Rahnama](https://www.hni.uni-paderborn.de/ism/mitarbeiter/155385986504753/), [Ralph Ewerth](https://www.tib.eu/de/forschung-entwicklung/visual-analytics/mitarbeiterinnen-und-mitarbeiter/ralph-ewerth/), [Hubertus Kohle](https://www.kunstgeschichte.uni-muenchen.de/personen/professoren_innen/kohle/index.html), and [Eyke Hüllermeier](https://www.hni.uni-paderborn.de/ism/mitarbeiter/112491383000284/).


## Contributing

Please report issues, feature requests, and questions to the [GitHub issue tracker](https://github.com/TIBHannover/iart/issues). We have a [Contributor Code of Conduct](https://github.com/TIBHannover/iart/blob/master/CODE_OF_CONDUCT.md). By participating in iART you agree to abide by its terms. -->
