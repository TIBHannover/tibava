# Description
This is the inference backend to the [Tibava](https://github.com/TIBHannover/tibava).\
This is where the actual machine learning models are running.

# Contribution guide

For the time being there aren't any strict contribution guides, but more will follow.

## Folder structure
- [`./analyser_interface_python`](./analyser_interface_python/) contains the Protobuf definitions used for the communication between the [backend](https://github.com/TIBHannover/tibava-backend/) and the inference server. Usually you won't be working on this directly
- [`./analyser_python`](./analyser_python/) contains the gRPC server listening for tasks from the backend and dispaches the tasks to the plugin manager defined in [`./inference_ray`](./inference_ray/)
- [`./data_python`](./data_python/) contains a lot of the type definitions used and the Tibava and their coressponding protobuf definitions.
- [`./inference_ray`](./inference_ray/) contains the main ray inference code, this where the ML models of the plugins are being executed. It's being provided with [ray serve](https://docs.ray.io/en/latest/serve/index.html)
- [`./utils_python`](./utils_python/) contains some of the helpers like plugins caching.