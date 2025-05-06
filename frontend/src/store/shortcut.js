import axios from '../plugins/axios';
import config from '../../app.config';
import { defineStore } from 'pinia'

import { usePlayerStore } from '@/store/player'

import * as Keyboard from "../plugins/keyboard.js";

export const useShortcutStore = defineStore('shortcut', {
    state: () => {
        return {

            shortcuts: {},
            shortcutList: [],
            shortcutByKeys: {},
            isLoading: false,
        }
    },
    getters: {

        all: (state) => {
            return state.shortcutList.map((id) => state.shortcuts[id]);
        },
        get: (state) => (id) => {
            return state.shortcuts[id];
        },
        getByKeys(state) {
            return (key) => {
                if (key in state.shortcutByKeys) {
                    return state.shortcutByKeys[key].map((id) => state.shortcuts[id]);
                }
                return []
            }
        },
    },
    actions: {
        async create({ key, videoId = null }) {
            if (this.isLoading) {
                return
            }
            this.isLoading = true

            const params = {
                key: key,
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
                .post(`${config.API_LOCATION}/shortcut/create`, params)
                .then((res) => {
                    if (res.data.status === "ok") {
                        const shortcut = res.data.entry
                        this.shortcuts[shortcut.id] = shortcut;
                        this.shortcutList.push(shortcut.id);
                        return res.data.entry.id;
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
                .get(`${config.API_LOCATION}/shortcut/list`, { params })
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
            this.shortcutByKeys = {}
            this.shortcuts = {}
            this.shortcutList = []
        },
        replaceAll(shortcuts) {
            this.shortcuts = {};
            this.shortcutList = [];
            shortcuts.forEach((e) => {
                this.shortcuts[e.id] = e;
                this.shortcutList.push(e.id);
            });
            this.updateKeyStore()
        },

        updateKeyStore() {
            // const annotationShortcutStore = useAnnotationShortcutStore();
            this.shortcutByKeys = {}
            this.all.forEach((e) => {
                const keys = Keyboard.generateKeysString(
                    e.keys
                );
                if (this.shortcutByKeys[keys] == null) {
                    this.shortcutByKeys[keys] = [];
                }
                this.shortcutByKeys[keys].push(e.id);
            });
        }
    },
})