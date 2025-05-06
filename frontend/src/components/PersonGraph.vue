<template>
    <v-dialog v-model="show" width="100%" persistent>
        <template v-slot:activator="{}">
            <v-btn @click="openGraph" style="color: rgb(175, 20, 20);">&nbsp; Show as Graph&nbsp;
                <v-icon color="primary">mdi-arrow-top-right-bold-box-outline</v-icon>
            </v-btn>
        </template>
        <v-card style="height: 90vh;">
            <v-card-title>Graph Visualization</v-card-title>
            <v-card-subtitle>Use the mouse to interact and zoom.</v-card-subtitle>

            <div v-if="loading" class="loading-container">
                <div class="spinner">
                    <i class="mdi mdi-loading mdi-spin"></i>
                </div>
                <div class="loading-text">Loading...</div>
            </div>
            <div id="graphContainer">
            </div>

            <v-card-actions variant="tonal">
                <v-row>
                    <v-col cols="2">
                        <v-text-field v-if="!loading" label="Minimum Cluster Size" v-model="filter_min_cluster_size" type="number"
                            @input="updateText"></v-text-field>
                    </v-col>

                    <v-col cols="2">
                        <v-text-field v-if="!loading" label="Minimum Relations" v-model="filter_min_relations" type="number"
                            @input="updateText"></v-text-field>
                    </v-col>

                    <v-spacer></v-spacer>

                    <v-col cols="5">
                        <v-label>Connect clusters if elements appeared in the same:</v-label>
                        <v-switch v-model="shotVisualization" label="Shot">
                            <template #prepend>
                                <v-label>Frame</v-label>
                            </template>

                        </v-switch>
                    </v-col>

                    <v-spacer></v-spacer>
                    
                    <v-col cols="1">
                        <v-btn @click="close">{{ $t("button.close") }}</v-btn>
                    </v-col>
                </v-row>
            </v-card-actions>
        </v-card>
    </v-dialog>
</template>

<script>
import "vis";
import { Network } from "vis-network";
import { DataSet } from "vis-data";
import { mapStores } from "pinia";
import { useShotStore } from "@/store/shot";
import { useClusterTimelineItemStore } from "../store/cluster_timeline_item";

export default {
    data() {
        return {
            show: false,
            nodes: null,
            edges: null,
            loading: true,
            cluster_min_size: 0,
            cluster_max_size: null,
            filter_min_cluster_size: 0,
            filter_min_relations: 0,
            network: null,
            data: null,
            options: null,
            debounceTimer: null,
            shotVisualization: true
        };
    },
    created() {
        this.prepareData();
    },
    mounted() {
        this.isGraphInitialized = true;
    },
    methods: {
        updateText() {
            // Clear the previous debounce timer, if any
            if (this.debounceTimer) {
                clearTimeout(this.debounceTimer);
            }

            // Set a new debounce timer to update the content after 500 milliseconds (adjust the delay as needed)
            this.debounceTimer = setTimeout(() => {
                // Your update logic here
                this.openGraph();
            }, 500);
        },
        prepareData() {
            if (this.clusterList.length == 0) {
                return;
            }

            this.clusterList.forEach((cluster) => {
                if (cluster.items.length < this.cluster_min_size) {
                    this.cluster_min_size = cluster.items.length;
                }
                if (cluster.items.length > this.cluster_max_size) {
                    this.cluster_max_size = cluster.items.length;
                }
                if (this.shotVisualization) {
                    cluster.shots = [];
                }
            });


            const shots = this.shotStore.shots;

            // get shots a face cluster is depicted in
            if (this.shotVisualization) {
                // for each shot
                for (const shot of shots) {
                    // iterate over all clusters
                    for (const cluster of Object.values(this.clusterList)) {
                        // if an object of the cluster is in the shot
                        for (const timestamp of this.timestamps(cluster)) {
                            if (timestamp >= shot.start & timestamp <= shot.end) {
                                if (!cluster.shots.includes(shot.id)) {
                                    cluster.shots.push(shot.id);
                                }
                            }
                        }
                    }
                }
            }


            // save nodes
            let dataset = [];
            this.clusterList.forEach((cluster) => {
                if (cluster.items.length < this.filter_min_cluster_size) {
                    return;
                }
                dataset.push({
                    id: cluster.id,
                    label: cluster.name,
                    value: cluster.items.length
                })
            });

            this.nodes = new DataSet(dataset);

            // save edges
            let connections = [];
            let checked = [];
            this.clusterList.forEach((cluster) => {
                if (cluster.items.length < this.filter_min_cluster_size) {
                    return;
                }

                this.clusterList.forEach((conn_cluster) => {
                    // do not add a relation to the node itself
                    if (cluster.id === conn_cluster.id) {
                        return;
                    }
                    // do not add relations between two clusters twice
                    if (checked.includes(String(cluster.id) + String(conn_cluster.id))) {
                        return;
                    }
                    let value = 0;
                    if (!this.shotVisualization) {
                        this.timestamps(cluster).forEach((timestamp) => {
                            if (this.timestamps(conn_cluster).includes(timestamp)) {
                                value++;
                            }
                        });
                    } else { // this.shotVisualization == true
                        cluster.shots.forEach((shot) => {
                            if (conn_cluster.shots.includes(shot)) {
                                value++;
                            }
                        })
                    }
                    if (value > this.filter_min_relations) {
                        connections.push({ from: cluster.id, to: conn_cluster.id, value: value, label: String(value) });
                    }
                    checked.push(String(cluster.id) + String(conn_cluster.id));
                    checked.push(String(conn_cluster.id) + String(cluster.id));
                });
            });
            this.edges = new DataSet(connections);

        },
        openGraph() {

            if (!this.isGraphInitialized) {
                return;
            }

            this.prepareData();
            // Destroy the existing network (if it exists)
            if (this.network) {
                this.network.destroy();
            }

            this.show = true;
            this.loading = true;

            this.$nextTick(() => {

                // Define your GraphML data here

                this.data = {
                    nodes: this.nodes,
                    edges: this.edges,
                };

                this.options = {
                    nodes: {

                        color: {
                            background: '#ffffff',
                            border: '#ae1313',
                            highlight: '#ae1313',
                        },
                        shape: 'dot',
                        font: {
                            size: 25,
                        },
                        borderWidth: 2,
                        shadow: true,
                        scaling: {
                            max: 50
                        }
                    },
                    edges: {
                        length: 300,
                        smooth: {
                            forceDirection: "none"
                        }
                    },
                };

                const container = document.getElementById("graphContainer");
                this.network = new Network(container, this.data, this.options);

                const functionThatDoesWhatYouNeed = () => {
                    this.loading = false;
                }
                this.network.on('afterDrawing', functionThatDoesWhatYouNeed);
            })
        },
        close() {
            this.show = false;
        },
        timestamps(cluster) {
            return cluster.items.map((i) => i.time);
        },
    },
    computed: {
        clusterList() {
            return this.clusterTimelineItemStore.latestFaceClustering();
        },
        ...mapStores(useClusterTimelineItemStore, useShotStore)
    },
    watch: {
        shotVisualization() {
            this.openGraph();
        }
    }
};
</script>


<style>
#graphContainer {
    align-items: center;
    justify-content: center;
    width: 100%;
    height: 79%;
    max-height: 75vh;
    margin-bottom: 5px;
}

.clusterslider {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    margin-bottom: 0px;
}

.loading-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 75vh;
    max-height: 75vh;
    overflow-y: auto;
    margin-bottom: 5px;
}

.spinner {
    font-size: 48px;
    color: #ac1414;
}

.loading-text {
    margin-top: 10px;
    font-size: 18px;
}
</style>