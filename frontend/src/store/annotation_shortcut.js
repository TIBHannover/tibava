import axios from '../plugins/axios';
import config from '../../app.config';
import { defineStore } from 'pinia'
import { usePlayerStore } from '@/store/player'
import { useShortcutStore } from './shortcut';

export const useAnnotationShortcutStore = defineStore('annotationShortcut', {
    state: () => {
        return {
            annotationShortcuts: {},
            annotationShortcutList: [],
            annotationShortcutByKeys: {},
            isLoading: false,
        }
    },
    getters: {

        all: (state) => {
            return state.annotationShortcutList.map(
                (id) => state.annotationShortcuts[id]
            );
        },
        get: (state) => (id) => {
            return state.annotationShortcuts[id];
        },
        forShortcut(state) {
            return (shortcutId) => {
                const annotationShortcuts = state.annotationShortcutList
                    .map((id) => state.annotationShortcuts[id])
                    .filter((e) => e.shortcut_id === shortcutId);

                if (annotationShortcuts.length > 0) {
                    return annotationShortcuts[0]
                }
                return null
            }
        },
    },
    actions: {
        async update({ annotationShortcuts, videoId = null }) {
            if (this.isLoading) {
                return
            }
            this.isLoading = true

            const params = {
                annotation_shortcuts: annotationShortcuts,
            };
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
                .post(`${config.API_LOCATION}/annotation/shortcut/update`, params)
                .then((res) => {
                    if (res.data.status === "ok") {
                        this.replaceAll(res.data.annotation_shortcuts);

                        const shortcutStore = useShortcutStore()
                        shortcutStore.replaceAll(res.data.shortcuts);
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
                .get(`${config.API_LOCATION}/annotation/shortcut/list`, {
                    params,
                })
                .then((res) => {
                    if (res.data.status === "ok") {
                        this.replaceAll(res.data.entries);

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
            this.annotationShortcutByKeys = {}
            this.annotationShortcuts = {}
            this.annotationShortcutList = []
        },
        replaceAll(annotationShortcuts) {
            this.annotationShortcuts = {};
            this.annotationShortcutList = [];
            annotationShortcuts.forEach((e) => {
                this.annotationShortcuts[e.id] = e;
                this.annotationShortcutList.push(e.id);
            });
        },
    },
})