# birdnet-frame

Sync a periodically updated image (e.g. a [fugleramme](https://github.com/arnegiacomo/fugleramme) bird collage) to a Samsung Frame TV's Art Mode.

A small daemon that:
1. Fetches an image from a configurable `SOURCE_URL`.
2. Converts it to JPEG.
3. Uploads it to a Samsung Frame TV and sets it as the active Art Mode picture.
4. Repeats on a configurable interval.

## Requirements

- A Samsung Frame TV with Art Mode, reachable on your local network.
- Art Mode must be enabled/available via the network API ([samsungtvws](https://github.com/xchwarze/samsung-tv-ws-api)).
- An HTTP endpoint that returns an image (e.g. [fugleramme](https://github.com/arnegiacomo/fugleramme), which defaults to port `8080`, a snapshot server, or a camera).
- Docker and Docker Compose (recommended), or Python 3.13+ if running directly.

## Configuration

All configuration is done via environment variables. Copy [`.env.example`](.env.example) to `.env` and fill in your own values:

```sh
cp .env.example .env
```

| Variable          | Required | Default | Description                                              |
|--------------------|----------|---------|------------------------------------------------------------|
| `TV_IP`            | yes      | -       | Local IP address of your Samsung Frame TV                  |
| `SOURCE_URL`       | yes      | -       | URL serving the image to display                            |
| `TV_PORT`          | no       | `8002`  | Samsung Frame TV Art Mode API port                          |
| `SYNC_INTERVAL`    | no       | `3600`  | Seconds between fetch/upload cycles                         |
| `REQUEST_TIMEOUT`  | no       | `10`    | HTTP timeout (seconds) when fetching the source image       |
| `FRAME_WIDTH`      | no       | `3840`  | Target canvas width the image is padded to                  |
| `FRAME_HEIGHT`     | no       | `2160`  | Target canvas height the image is padded to                 |
| `FRAME_BACKGROUND_COLOR` | no | `#f2ede2` | Padding color used for images that don't match the frame's aspect ratio |
| `AUTO_SELECT_IMAGE` | no  | `true`  | Whether to select the uploaded image as the active Art Mode picture |
| `UPLOAD_TIMEOUT`   | no       | `300`   | Give up on a stuck TV connection after this many seconds     |
| `DATA_DIR`         | no       | `data`  | Directory where the last uploaded image's content id is persisted    |
| `HOST_DATA_DIR`    | no       | `./data`| Host path mounted to `DATA_DIR` when running via Docker Compose      |
| `LOG_LEVEL`        | no       | `INFO`  | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`)      |

`TV_IP` and `SOURCE_URL` have no defaults; the daemon exits at startup if either is missing.

Only one image is kept on the TV at a time: after each successful upload, the previous image is deleted. The active image's content id is persisted under `DATA_DIR` (mounted as a volume in Docker Compose) so this still works after a container restart.

## Running with Docker Compose

```sh
cp .env.example .env
# edit .env with your TV_IP and SOURCE_URL
docker compose up -d --build
```

A prebuilt image is also published to the GitHub Container Registry on every push to `main` and on version tags (see [.github/workflows/docker-publish.yml](.github/workflows/docker-publish.yml)):

```sh
docker pull ghcr.io/icecoldfire/birdnet-frame:latest
```

View logs:

```sh
docker compose logs -f
```

## Running locally

This project uses [uv](https://docs.astral.sh/uv/) for dependency management.

```sh
uv sync
cp .env.example .env
# edit .env with your TV_IP and SOURCE_URL
uv run main.py
```

A local `.env` file is loaded automatically (via [python-dotenv](https://github.com/theskumar/python-dotenv)) when present. In Docker, variables come from `env_file` in `docker-compose.yml` instead.

## Development

Linting ([ruff](https://github.com/astral-sh/ruff)) and type checking ([ty](https://github.com/astral-sh/ty)) run via [prek](https://github.com/j178/prek), a fast pre-commit hook manager compatible with `.pre-commit-config.yaml`.

```sh
uv sync
uv run prek install   # install the git hook, runs automatically on commit
uv run prek run --all-files   # run all hooks manually
```

## Security notes

- Never commit your `.env` file — it contains your local network configuration. It is excluded via [`.gitignore`](.gitignore).
- `SOURCE_URL` is fetched with a fixed timeout and no redirect/content validation beyond image decoding; only point it at a trusted source you control.
