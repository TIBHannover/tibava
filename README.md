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
    git clone --recurse-submodules https://github.com/TIBHannover/tibava.git
    cd tibava
    ```

2. Run `install.sh` to download and extract models:
    ```sh
    mkdir data/cache
    mkdir data/analyser
    mkdir data/media
    mkdir data/tmp
    mkdir data/predictions
    mkdir data/backend_cache
    wget wget https://tib.eu/cloud/s/xLXEEsf99KPYcoW/download/models.tar.gz
    tar -xf models.tar.gz --directory data/
    ```

3. Build and start the container:
    ```sh
    sudo docker-compose up --build
    ```

4. Apply database migrations and build frontend packages:
    ```sh
    sudo docker-compose exec backend python3 manage.py migrate auth
    sudo docker-compose exec backend python3 manage.py migrate
    sudo docker-compose exec frontend npm install
    sudo docker-compose exec frontend npm run build
    ```

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

### Integration of a new plugin
1. Build the plugin
   1. Create a new file in `analyser/inference_ray/src/plugins/`
   2. Create a class inhereting from `AnalyserPlugin` with an `__init__` and a `call` method (signature and structure can be found in other plugins)
   3. Register your class with a unique name using the decorator `@AnalyserPluginManager.export("your_plugin_name")`
   4. Specify Input and Output data types in objects `requires` and `provides` (can be found in `analyser/data_python/src/plugins/`)
   5. Import needed packages and load models inside the `call` method
   6. Add your new plugin to `analyser/inference_ray/deploy.yml` and to `analyser/inference_ray/deploy.cuda.yml` by adding:
   ```
   - name: your_plugin_name
    route_prefix: /your_plugin_name
    import_path: main:app_builder
    args:
      model: your_plugin_name
      data_path: /data
      params: {}
    deployments:
      - name: Deployment
        autoscaling_config:
          min_replicas: 0
        ray_actor_options:
          num_cpus: 2
          runtime_env:
            pip:
              - imported_dummy_package1==1.0.0
              - imported_dummy_package2==2.0.1
   ```
   - Rerun (sudo) `docker-compose up --build` to include your new plugin
   - Use logging.error("message") for debugging purposes inside your plugin
   - Example of needed Stub for call method: 
   ```
   with inputs as input_data, data_manager.create_data(
            "OutputDataType" # Has to be passed as a String e.g. "ListData"
        ) as output_data:
            # e.g. add AnnotationData entry to ListData object
            with output_data.create_data("AnnotationData") as ann_data:
                ann_data.annotations.extend(your_annotation) # e.g. data type Annotation
                ann_data.name = "name of data entry"

            self.update_callbacks(callbacks, progress=1.0)
            return {"annotations": output_data} # example of returning object with "annotations"
    ```
2. Add plugin to backend
   1. Create a new file in `backend/backend/tasks/`
   2. Include the new file in `backend/backend/tasks/__init__.py`
   3. Create a class inhereting from `Parser` with an `__init__` method to parse plugin parameters and register it with: `@PluginManager.export_parser("your_plugin_name")`
   4. Create a class inhereting from `Task` with an `__init__` and a `__call__` method to include your plugin and register it with: ``@PluginManager.export_plugin("your_plugin_name")`
   5. Look at other plugins to get a notion of sophisticated class/method structures
3. Make plugin accessable in frontend
   1. Add plugin to a group in `frontend/src/components/ModalPlugin.vue` with:
   ```
   {
        name: this.$t("modal.plugin.your_plugin_name.plugin_name"),
        description: this.$t("modal.plugin.your_plugin_name.plugin_description"),
        icon: "your_plugin_icon", // from https://pictogrammers.com/library/mdi/
        plugin: "your_plugin_name",
        id: 0, // unique integers in ascending order
        parameters: [], // parameters to control adjustable plugin behaviour (lookup types in other plugins)
        optional_parameters: [], // parameters in an extendable window
   }
   ```
   2. Add plugin name, description... in `frontend/src/locales/en.json`:
   ```
   "your_plugin_name": {
        "plugin_name": "Your Plugin Name",
        "plugin_description": "Your plugin description.",
        // ... add more custom variables if needed
   }
   ```
   3. Adjust name for run history in `frontend/src/components/History.vue` inside of pluginName(type) {...} by adding:
   ```
   if (type === "your_plugin_name") {
        return this.$t("modal.plugin.your_plugin_name.plugin_name");
      }
   ```

<!-- ## About the project

iART was funded by the [DFG](https://gepris.dfg.de/gepris/projekt/415796915) from 2019 to 2021. Our team consists of [Matthias Springstein](https://www.tib.eu/de/forschung-entwicklung/visual-analytics/mitarbeiterinnen-und-mitarbeiter/matthias-springstein/), [Stefanie Schneider](https://www.kunstgeschichte.uni-muenchen.de/personen/wiss_ma/schneider/index.html), [Javad Rahnama](https://www.hni.uni-paderborn.de/ism/mitarbeiter/155385986504753/), [Ralph Ewerth](https://www.tib.eu/de/forschung-entwicklung/visual-analytics/mitarbeiterinnen-und-mitarbeiter/ralph-ewerth/), [Hubertus Kohle](https://www.kunstgeschichte.uni-muenchen.de/personen/professoren_innen/kohle/index.html), and [Eyke Hüllermeier](https://www.hni.uni-paderborn.de/ism/mitarbeiter/112491383000284/).


## Contributing

Please report issues, feature requests, and questions to the [GitHub issue tracker](https://github.com/TIBHannover/iart/issues). We have a [Contributor Code of Conduct](https://github.com/TIBHannover/iart/blob/master/CODE_OF_CONDUCT.md). By participating in iART you agree to abide by its terms. -->
