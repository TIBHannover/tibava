import Vue from "vue";
import axios from "../plugins/axios";
import config from "../../app.config";
import { usePlayerStore } from "./player";
import { usePluginRunStore } from "./plugin_run";

import { defineStore } from "pinia";

export const useClusterTimelineItemStore = defineStore("clusterTimelineItem", {
    state: () => {
        return {
            clusterTimelineItems: {},
            isLoading: false,
            selectedPlaceClustering: null,
            selectedFaceClustering: null,
        };
    },
    getters: {
        faceClusteringList() {

            const pluginRunStore = usePluginRunStore();
            const playerStore = usePlayerStore();

            return pluginRunStore
                .forVideo(playerStore.videoId)
                .filter((e) => e.type == "face_clustering" && e.status == "DONE")
                .sort((a, b) => {
                    return new Date(b.date) - new Date(a.date);
                }).map((e) => {
                    return {
                        index: e.id,
                        name: new Date(e.date)
                    }
                });

        },
        placeClusteringList() {

            const pluginRunStore = usePluginRunStore();
            const playerStore = usePlayerStore();

            return pluginRunStore
                .forVideo(playerStore.videoId)
                .filter((e) => e.type == "place_clustering" && e.status == "DONE")
                .sort((a, b) => {
                    return new Date(b.date) - new Date(a.date);
                }).map((e) => {
                    return {
                        index: e.id,
                        name: new Date(e.date)
                    }
                });

        },
        latestPlaceClustering(state) {
            return () => {
                const pluginRunStore = usePluginRunStore();
                const playerStore = usePlayerStore();

                let place_clustering = pluginRunStore
                    .forVideo(playerStore.videoId)
                    .filter((e) => e.type == "place_clustering" && e.status == "DONE")
                    .sort((a, b) => {
                        return new Date(b.date) - new Date(a.date);
                    })
                    ;
                if (!place_clustering.length) {
                    return [];
                }
                return Object.values(state.clusterTimelineItems)
                    .filter((cti) => cti.plugin_run === state.selectedPlaceClustering)
                    .sort((a, b) => b.items.length - a.items.length);
            }
        },
        latestFaceClustering(state) {
            return () => {
                const pluginRunStore = usePluginRunStore();
                const playerStore = usePlayerStore();

                let face_clustering = pluginRunStore
                    .forVideo(playerStore.videoId)
                    .filter((e) => e.type == "face_clustering" && e.status == "DONE")
                    .sort((a, b) => {
                        return new Date(b.date) - new Date(a.date);
                    })
                    ;
                if (!face_clustering.length) {
                    return [];
                }
                return Object.values(state.clusterTimelineItems)
                    .filter((cti) => cti.plugin_run === state.selectedFaceClustering)
                    .sort((a, b) => b.items.length - a.items.length);
            }
        },
    },
    actions: {
        async setSelectedPlaceClustering({ videoId = null, pluginRunId = null }) {
            this.selectedPlaceClustering = pluginRunId;

            if (this.isLoading) {
                return;
            }
            this.isLoading = true;

            //use video id or take it from the current video
            let params = { plugin_run_id: pluginRunId };
            if (videoId) {
                params.video_id = videoId;
            } else {
                const playerStore = usePlayerStore();
                const videoId = playerStore.videoId;
                if (videoId) {
                    params.video_id = videoId;
                }
            }

            return axios
                .post(`${config.API_LOCATION}/video/analysis/setselectedplaceclustering`, params)
                .then((res) => {
                    if (res.data.status === "ok") {
                    }
                })
                .catch(() => { })
                .finally(() => {
                    this.isLoading = false;
                });
        },
        async setSelectedFaceClustering({ videoId = null, pluginRunId = null }) {
            this.selectedFaceClustering = pluginRunId;

            if (this.isLoading) {
                return;
            }
            this.isLoading = true;

            //use video id or take it from the current video
            let params = { plugin_run_id: pluginRunId };
            if (videoId) {
                params.video_id = videoId;
            } else {
                const playerStore = usePlayerStore();
                const videoId = playerStore.videoId;
                if (videoId) {
                    params.video_id = videoId;
                }
            }

            return axios
                .post(`${config.API_LOCATION}/video/analysis/setselectedfaceclustering`, params)
                .then((res) => {
                    if (res.data.status === "ok") {
                    }
                })
                .catch(() => { })
                .finally(() => {
                    this.isLoading = false;
                });
        },

        async fetchAll(videoId) {
            if (videoId == null || videoId == undefined) {
                const playerStore = usePlayerStore();
                videoId = playerStore.videoId;
            }
            if (this.isLoading) {
                return
            }
            this.isLoading = true

            let promises = [];
            const fetch_item = axios.get(`${config.API_LOCATION}/cluster/timeline/item/fetch`, { params: { video_id: videoId } })
                .then((res) => {
                    if (res.data.status === "ok") {
                        this.replaceStore(res.data.entries);
                    }
                    else {
                        console.log("error in fetchAll clusterTimelineItems");
                        console.log(res.data);
                    }
                })
            promises.push(fetch_item)

            const fetch_selected = axios
                .get(`${config.API_LOCATION}/video/analysis/get`, { params: { video_id: videoId } })
                .then((res) => {
                    if (res.data.status === "ok") {
                        this.selectedPlaceClustering = res.data.entry.selected_place_clustering;
                        this.selectedFaceClustering = res.data.entry.selected_face_clustering;
                    }
                })
            promises.push(fetch_selected)

            return Promise.all(promises).finally(() => {
                this.isLoading = false;
            });
        },
        async merge({ cluster_from_id, cluster_to_id }) {
            if (this.isLoading) {
                return;
            }
            this.isLoading = true;

            const cluster_from = this.clusterTimelineItems[cluster_from_id];
            const cluster_to = this.clusterTimelineItems[cluster_to_id];

            let params = {
                from_id: cluster_from.id,
                to_id: cluster_to.id
            };

            return axios
                .post(`${config.API_LOCATION}/cluster/timeline/item/merge`, params)
                .then((res) => {
                    if (res.data.status === "ok") {
                        Vue.set(
                            cluster_to,
                            "items",
                            cluster_to.items.concat(cluster_from.items)
                        );
                        this.deleteFromStore(cluster_from_id);
                    }
                })
                .finally(() => {
                    this.isLoading = false;
                });
        },
        async rename({ cluster_id, name }) {
            if (this.isLoading) {
                return;
            }
            this.isLoading = true;


            const updated_ctis = { ...this.clusterTimelineItems };
            updated_ctis[cluster_id].name = name;
            Vue.set(this, "clusterTimelineItems", updated_ctis);

            let params = {
                cti_id: this.clusterTimelineItems[cluster_id].id,
                name: name,
            };

            return axios
                .post(`${config.API_LOCATION}/cluster/timeline/item/rename`, params)
                .then((res) => {
                    if (res.data.status !== "ok") {
                        console.log("Error in CTI Rename");
                        console.log(res.data);
                    }
                })
                .finally(() => {
                    this.isLoading = false;
                });
        },
        async create(name, video_id, plugin_run, type) {
            if (this.isLoading) {
                return;
            }
            this.isLoading = true;

            const params = {
                name: name,
                video_id: video_id,
                plugin_run: plugin_run,
                type: type
            };

            return axios
                .post(`${config.API_LOCATION}/cluster/timeline/item/create`, params)
                .then((res) => {
                    if (res.data.status === "ok") {
                        this.addToStore(res.data.entry);
                        return res.data.entry;
                    }
                    else {
                        console.log("Error in clusterTimelineItem/create");
                        console.log(res.data);
                    }
                })
                .finally(() => {
                    this.isLoading = false;
                });

        },
        async delete(cluster_id) {
            if (this.isLoading) {
                return;
            }
            this.isLoading = true;

            let params = {
                id: this.clusterTimelineItems[cluster_id].id,
            };

            return axios
                .post(`${config.API_LOCATION}/cluster/timeline/item/delete`, params)
                .then((res) => {
                    if (res.data.status === "ok") {
                        this.deleteFromStore(cluster_id);
                    }
                })
                .finally(() => {
                    this.isLoading = false;
                });
        },
        async deleteItems(cluster_id, item_ids) {
            if (this.isLoading) {
                return;
            }
            this.isLoading = true;

            let params = {
                item_ids: item_ids,
                cluster_id: cluster_id
            };

            return axios
                .post(`${config.API_LOCATION}/cluster/item/delete`, params)
                .then((res) => {
                    if (res.data.status === "ok") {
                        Vue.set(this.clusterTimelineItems[cluster_id], "items", this.clusterTimelineItems[cluster_id].items.filter((i) => !item_ids.includes(i.id)));
                    }
                    else {
                        console.log("Error in clusterTimelineItem/delete");
                        console.log(res.data);
                    }
                })
                .finally(() => {
                    this.isLoading = false;
                });
        },
        moveItemsToCluster(oldClusterId, itemsIds, newClusterId) {
            if (this.isLoading) {
                return;
            }
            this.isLoading = true;

            let params = {
                item_ids: itemsIds,
                new_cluster_id: this.clusterTimelineItems[newClusterId].id
            };

            return axios
                .post(`${config.API_LOCATION}/cluster/item/move`, params)
                .then((res) => {
                    if (res.data.status === "ok") {
                        const oldClusterItems = this.clusterTimelineItems[oldClusterId].items.filter((i) => itemsIds.indexOf(i.id) < 0)
                        const items = this.clusterTimelineItems[oldClusterId].items.filter((i) => itemsIds.indexOf(i.id) >= 0)
                        Vue.set(this.clusterTimelineItems[oldClusterId], "items", oldClusterItems);
                        Vue.set(this.clusterTimelineItems[newClusterId], "items",
                            [...this.clusterTimelineItems[newClusterId].items, ...items]
                        );
                    }
                    else {
                        console.log("Error in clusterTimelineItem/move");
                        console.log(res.data);
                    }
                })
                .finally(() => {
                    this.isLoading = false;
                });
        },
        deleteFromStore(cluster_id) {
            Vue.delete(this.clusterTimelineItems, cluster_id);
        },
        addToStore(clusterTimelineItem) {
            Vue.set(this.clusterTimelineItems, clusterTimelineItem.cluster_id, clusterTimelineItem);
        },
        replaceStore(items) {
            this.clearStore();
            items.forEach((e) => { this.addToStore(e) });
        },
        clearStore() {
            Object.keys(this.clusterTimelineItems).forEach(key => {
                Vue.delete(this.clusterTimelineItems, key);
            });
        }

    },
});