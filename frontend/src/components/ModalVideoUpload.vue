<template>
  <v-card :class="['d-flex', 'flex-column', 'pa-2', 'ma-4']" style="
            text-align: center;
          " flat color="transparent" width="300">
    <v-dialog v-model="dialog" max-width="1000">
      <template v-slot:activator="{ on, attrs }">
        <v-btn :disabled="!canUpload" color="primary" v-bind="attrs" v-on="on">
          Upload new video<v-icon right>{{ "mdi-plus-circle" }}</v-icon>
        </v-btn>
      </template>
      <v-card>
        <v-toolbar color="primary" dark>Upload new video</v-toolbar>
        <v-card-text>
          <v-form>
            <v-text-field v-model="video.title" :counter="120" label="Video title" required></v-text-field>
            <v-file-input v-model="video.file" :rules="[validateFile]" label="Select a video file [mp4]" filled
              prepend-icon="mdi-movie-filter"></v-file-input>

            <v-checkbox v-model="checkbox" label="Do you agree with the terms of services?" required>
            </v-checkbox>

            <v-progress-linear v-if="isUploading" :value="uploadingProgress" class="mb-2"></v-progress-linear>

            <v-btn class="mr-4" :disabled="disabled" @click="upload_video">
              Upload
            </v-btn>
            <v-btn @click="dialog = false">Close</v-btn>
          </v-form>
        </v-card-text>
      </v-card>
    </v-dialog>
    <span v-if="!canUpload" class="red--text">You have uploaded the maximum amount of videos that you are allowed to. If
      you require more, please contact eric.mueller@tib.eu.</span>
    <span v-if="canUpload">Videos uploaded: {{ num_videos }} out of {{ allowance }}</span>
    <span v-if="canUpload">Maximum file size: {{ max_size_in_words }}</span>


  </v-card>
</template>

<script>


import { mapStores } from 'pinia'
import { useVideoUploadStore } from "@/store/video_upload"
import { useUserStore } from "@/store/user"
import { useVideoStore } from "@/store/video"

export default {
  data() {
    return {
      video: {},
      analysers: [
        {
          label: "Shot Detection",
          disabled: false,
          model: "shotdetection",
        },
      ],
      selected_analysers: ["shotdetection"],
      checkbox: false,
      dialog: false,
      file_valid: false,
    };
  },
  computed: {
    canUpload() {
      return this.userStore.allowance > this.videoStore.all.length;
    },
    disabled() {
      return !this.checkbox || !this.file_valid || this.uploadingProgress != 0;
    },
    isUploading() {
      return this.videoUploadStore.isUploading;
    },
    uploadingProgress() {
      return this.videoUploadStore.progress;
    },
    allowance() {
      return this.userStore.allowance;
    },
    num_videos() {
      return this.videoStore.all.length;
    },
    max_size_in_words() {
      var size = this.userStore.max_video_size;
      var extension_id = 0;
      var extensions = [" B", " kB", " MB", " GB"]
      while (size > 1024) {
        size = (size / 1024).toFixed(2);
        extension_id++;
      }
      return size + extensions[extension_id];
    },
    max_size() {
      console.log(this.userStore.max_video_size);
      return this.userStore.max_video_size;
    },
    ...mapStores(useVideoUploadStore, useUserStore, useVideoStore)
  },
  methods: {
    validateFile(file) {
      if (!file) {
        this.file_valid = false;
        return 'Please select a file.';
      }
      if (file.size > this.max_size) {
        this.file_valid = false;
        return 'File exceeds your maximum file size of ' + this.max_size_in_words;
      }
      if (!file.name.endsWith(".mp4")) {
        this.file_valid = false;
        return 'File is not in the .mp4 format.'
      }

      this.file_valid = true;
      return true;
    },
    async upload_video() {
      const params = {
        video: this.video,
        analyser: this.selected_analysers,
      };

      await this.videoUploadStore.upload(params);
      //   TODO wait until signal is fired

      this.dialog = false;
      this.file_valid = false;
    },
  },
};
</script>
