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
    mkdir -p data/models
    wget https://tib.eu/cloud/s/T6cKP4gok8ARWGS/download/models.tar.gz
    tar -xf models.tar.gz --directory data/models
    mkdir -p data/tmp
    mkdir -p data/predictions/thumbnails
    mkdir -p data/media
    mkdir -p data/analyser
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


<!-- ## About the project

iART was funded by the [DFG](https://gepris.dfg.de/gepris/projekt/415796915) from 2019 to 2021. Our team consists of [Matthias Springstein](https://www.tib.eu/de/forschung-entwicklung/visual-analytics/mitarbeiterinnen-und-mitarbeiter/matthias-springstein/), [Stefanie Schneider](https://www.kunstgeschichte.uni-muenchen.de/personen/wiss_ma/schneider/index.html), [Javad Rahnama](https://www.hni.uni-paderborn.de/ism/mitarbeiter/155385986504753/), [Ralph Ewerth](https://www.tib.eu/de/forschung-entwicklung/visual-analytics/mitarbeiterinnen-und-mitarbeiter/ralph-ewerth/), [Hubertus Kohle](https://www.kunstgeschichte.uni-muenchen.de/personen/professoren_innen/kohle/index.html), and [Eyke Hüllermeier](https://www.hni.uni-paderborn.de/ism/mitarbeiter/112491383000284/).


## Contributing

Please report issues, feature requests, and questions to the [GitHub issue tracker](https://github.com/TIBHannover/iart/issues). We have a [Contributor Code of Conduct](https://github.com/TIBHannover/iart/blob/master/CODE_OF_CONDUCT.md). By participating in iART you agree to abide by its terms. -->
