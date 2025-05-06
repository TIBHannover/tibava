import Vue from "vue";
import axios from '../plugins/axios';
import config from '../../app.config';
import { defineStore } from 'pinia';
import { usePlayerStore } from "@/store/player";

export const useAnnotationCategoryStore = defineStore('annotationCategory', {
    state: () => {
        return {
            annotationCategories: {},
            isLoading: false,
        }
    },
    getters: {
        all: (state) => {
            return Object.values(state.annotationCategories);
        },
        get: (state) => (id) => {
            return state.annotationCategories[id];
        }
    },
    actions: {
        async create({ name, color, videoId = null }) {
            if (this.isLoading) {
                return
            }
            this.isLoading = true

            const params = {
                name: name,
                color: color
            }
            if (videoId) {
                params.video_id = videoId;
            }
            else {
                const playerStore = usePlayerStore();
                const videoId = playerStore.videoId;
                if (videoId) {
                    params.video_id = videoId;
                }
            }

            return axios.post(`${config.API_LOCATION}/annotation/category/create`, params)
                .then((res) => {
                    if (res.data.status === 'ok') {
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
        async fetchForVideo({ videoId = null }) {
            if (this.isLoading) {
                return
            }
            this.isLoading = true

            let params = {}

            //use video id or take it from the current video
            if (videoId) {
                params.video_id = videoId;
            }
            else {
                const playerStore = usePlayerStore();
                const videoId = playerStore.videoId;
                if (videoId) {
                    params.video_id = videoId;
                }
            }
            return axios.get(`${config.API_LOCATION}/annotation/category/list`, { params })
                .then((res) => {
                    if (res.data.status === 'ok') {
                        this.updateStore(res.data.entries);
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


        clearStore() {
            Object.keys(this.annotationCategories ).forEach(key => {
                Vue.delete(this.annotationCategories , key);
            });
        },
        addToStore(annotationCategories) {
            annotationCategories.forEach((e) => {
                Vue.set(this.annotationCategories, e.id, e);
            });
        },

        updateStore(annotationCategories) {
            annotationCategories.forEach((e) => {
                if (e.id in this.annotationCategories) {
                    return;
                }
                Vue.set(this.annotationCategories, e.id, e);
            });
        }
    },
})