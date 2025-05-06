import Vue from 'vue';
import axios from '../plugins/axios';
import config from '../../app.config';
import { defineStore } from 'pinia'
import { usePlayerStore } from "./player";
import { useAnnotationCategoryStore } from "@/store/annotation_category";


export const useAnnotationStore = defineStore('annotation', {
    state: () => {
        return {
            annotations: {},
            isLoading: false,
        }
    },
    getters: {
        nonTranscripts: (state) => {
            const annotationCategoryStore = useAnnotationCategoryStore();
            return Object.values(state.annotations)
                         .filter((a) => !annotationCategoryStore.get(a.category_id) || annotationCategoryStore.get(a.category_id).name !== "Transcript");
        },
        all: (state) => {
            return Object.values(state.annotations);
        },
        get: (state) => (id) => {
            return state.annotations[id];
        },
    },
    actions: {

        async create({ name, color, categoryId, videoId = null }) {
            if (this.isLoading) {
                return
            }
            this.isLoading = true

            let params = {
                name: name,
                color: color,
            };
            if (categoryId) {
                params["category_id"] = categoryId;
            }

            //use video id or take it from the current video
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
                .post(`${config.API_LOCATION}/annotation/create`, params)
                .then((res) => {
                    if (res.data.status === "ok") {
                        this.addToStore([res.data.entry]);
                        return res.data.entry.id;
                    }
                })
                .finally(() => {
                    this.isLoading = false;
                })
            // .catch((error) => {
            //     const info = { date: Date(), error, origin: 'collection' };
            //     commit('error/update', info, { root: true });
            // });
        },
        async change({ annotationId, name, color, categoryId }) {
            if (this.isLoading) {
                return
            }
            this.isLoading = true

            let params = {
                annotation_id: annotationId,
                color: color,
                name: name,
            };
            if (categoryId) {
                params["category_id"] = categoryId;
            }

            return axios
                .post(`${config.API_LOCATION}/annotation/update`, params)
                .then((res) => {
                    if (res.data.status === "ok") {
                        this.updateInStore([
                            {
                                id: annotationId,
                                color: color,
                                name: name,
                                category_id: categoryId,
                            },
                        ]);
                        // return res.data.entry.id;
                    }
                })
                .finally(() => {
                    this.isLoading = false;
                });
            // .catch((error) => {
            //     const info = { date: Date(), error, origin: 'collection' };
            //     commit('error/update', info, { root: true });
            // });
        },
        // listAdd( segment_hash_id) {
        //     const params = {
        //         hash_id: segment_hash_id,
        //         annotation: annotation
        //     }
        //     axios.post(`${config.API_LOCATION}/annotation_list`, params)
        //         .then((res) => {
        //             if (res.data.status === 'ok') {
        //                 commit('add', params);
        //             }
        //         })
        //         .catch((error) => {
        //             const info = { date: Date(), error, origin: 'collection' };
        //             commit('error/update', info, { root: true });
        //         });
        // },
        async fetchForVideo({ videoId = null }) {
            if (this.isLoading) {
                return
            }
            this.isLoading = true

            let params = {};

            //use video id or take it from the current video
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
                .get(`${config.API_LOCATION}/annotation/list`, { params })
                .then((res) => {
                    if (res.data.status === "ok") {
                        this.updateStore(res.data.entries);
                    }
                })
                .finally(() => {
                    this.isLoading = false;
                });
            // .catch((error) => {
            //     const info = { date: Date(), error, origin: 'collection' };
            //     commit('error/update', info, { root: true });
            // });
        },
        clearStore() {
            Object.keys(this.annotations).forEach(key => {
                Vue.delete(this.annotations, key);
            });
        },
        updateInStore(annotations) {
            const newAnnotations = { ...this.annotations };
            annotations.forEach((e) => {
                Vue.set(newAnnotations, e.id, e);
            });
            this.annotations = newAnnotations;
        },
        addToStore(annotations) {
            annotations.forEach((e) => {
                Vue.set(this.annotations, e.id, e);
            });
        },
        updateStore(annotations) {
            annotations.forEach((e) => {
                if (e.id in this.annotations) {
                    return;
                }
                Vue.set(this.annotations, e.id, e);
            });
        },
    },
})