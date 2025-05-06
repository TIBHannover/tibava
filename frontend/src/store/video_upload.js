import axios from '../plugins/axios';
import config from '../../app.config';
import { defineStore } from 'pinia'
import { useVideoStore } from './video'
import { useErrorStore } from './error'

export const useVideoUploadStore = defineStore('videoUpload', {
    state: () => {
        return {
            isUploading: false,
            progress: 0.0,
        }
    },
    getters: {
        pluginRunByVideoId: (state) => {
            return (videoId) => {
                return state.pluginRunList.map(id => state.pluginRuns[id]).filter(e => e.video_id === videoId)
            }
        }
    },
    actions: {
        async upload(params) {
            const videoStore = useVideoStore();
            const formData = new FormData();
            formData.append("file", params.video.file);
            formData.append("title", params.video.title);
            formData.append("analyser", params.analyser);
            this.isUploading = true;
            // commit('loading/update', true, { root: true });
            return axios
                .post(`${config.API_LOCATION}/video/upload`, formData, {
                    headers: { "Content-Type": "multipart/form-data" },
                    onUploadProgress: (event) => {
                        console.log(JSON.stringify(event));
                        const totalLength = event.lengthComputable
                            ? event.total
                            : event.target.getResponseHeader("content-length") ||
                            event.target.getResponseHeader("x-decompressed-content-length");
                        console.log("onUploadProgress", totalLength);
                        if (totalLength !== null) {
                            const progress = Math.round((event.loaded * 100) / totalLength);
                            this.progress = progress;
                        }
                    },
                })
                .then((res) => {
                    console.log(res);
                    if (res.data.status === "ok") {
                        res.data.entries.forEach((entry) => {
                            videoStore.addToStore(entry);
                        });
                    }
                })
                .catch((error) => {
                    const errorStore = useErrorStore();
                    if (error.response.data) {
                        if (error.response.data.hasOwnProperty("type")) {
                            errorStore.setError("video_upload", error.response.data.type);
                            return
                        }
                    }
                    errorStore.setError("video_upload", "unknown");

                })
                .finally(() => {
                    this.isUploading = false;
                    this.progress = 0;
                })
        },
    },
})