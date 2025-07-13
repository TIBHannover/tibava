<template>
  <v-card
    :class="['d-flex', 'flex-column', 'pa-2', 'ma-4']"
    style="text-align: center"
    flat
    color="transparent"
  >
    <v-dialog v-model="dialog" width="90%" height="600px" max-height="90%">
      <template v-slot:activator="{ on, attrs }">
        <v-btn :disabled="!canUpload" color="primary" v-bind="attrs" v-on="on">
          {{ $t("modal.video.upload.link")
          }}<v-icon right>{{ "mdi-plus-circle" }}</v-icon>
        </v-btn>
      </template>
      <v-card>
        <v-card-title class="mb-2">
          {{ $t("modal.video.upload.title") }}

          <v-btn icon @click.native="show = false" absolute top right>
            <v-icon>mdi-close</v-icon>
          </v-btn>
          <v-tabs v-model="tab" fixed-tabs>
            <v-tabs-slider></v-tabs-slider>

            <v-tab> {{ $t("modal.video.upload.tab_legal") }} </v-tab>
            <v-tab :disabled="!checkbox">
              {{ $t("modal.video.upload.tab_upload") }}
            </v-tab>
          </v-tabs>
        </v-card-title>
        <!-- <v-card-title>
          <v-toolbar color="primary" dark>
            {{ $t("modal.video.upload.title") }}
            <template v-slot:extension>
              <v-tabs v-model="tab" align-with-title fixed-tabs dark>
                <v-tabs-slider></v-tabs-slider>

                <v-tab> {{ $t("modal.video.upload.tab_legal") }} </v-tab>
                <v-tab> {{ $t("modal.video.upload.tab_upload") }} </v-tab>
              </v-tabs>
            </template>
          </v-toolbar>
        </v-card-title> -->
        <v-card-text>
          <v-tabs-items v-model="tab">
            <v-tab-item>
              <h1 class="mt-2">{{ $t("modal.video.upload.terms.title") }}</h1>
              <p v-html="$t('modal.video.upload.terms.content')"></p>

              <v-form>
                <v-checkbox
                  v-model="checkbox"
                  label="Do you agree with the terms of services?"
                  required
                >
                </v-checkbox>
              </v-form>
            </v-tab-item>
            <v-tab-item>
              <v-form>
                <v-text-field
                  v-model="video.title"
                  :counter="120"
                  label="Video title"
                  required
                ></v-text-field>
                <v-file-input
                  v-model="video.file"
                  :rules="[validateFile]"
                  label="Select a video file [mp4]"
                  filled
                  prepend-icon="mdi-movie-filter"
                ></v-file-input>

                <v-progress-linear
                  v-if="isUploading"
                  :value="uploadingProgress"
                  class="mb-2"
                ></v-progress-linear>
              </v-form>
            </v-tab-item>
          </v-tabs-items>
        </v-card-text>
        <v-card-actions class="pt-0">
          <v-btn
            v-if="tab == 0"
            class="mr-4"
            :disabled="!checkbox"
            @click="tab++"
          >
            {{ $t("modal.video.upload.continue") }}
          </v-btn>
          <v-btn
            v-if="tab == 1"
            class="mr-4"
            :disabled="disabled"
            @click="upload_video"
          >
            {{ $t("modal.video.upload.upload") }}
          </v-btn>
          <v-btn @click="dialog = false">{{
            $t("modal.video.upload.close")
          }}</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
    <span v-if="!canUpload" class="red--text"
      >You have uploaded the maximum amount of videos that you are allowed to.
      If you require more, please contact eric.mueller@tib.eu.</span
    >
    <span v-if="canUpload"
      >Videos uploaded: {{ num_videos }} out of {{ allowance }}</span
    >
    <span v-if="canUpload">Maximum file size: {{ max_size_in_words }}</span>
  </v-card>
</template>

<script>
import { mapStores } from "pinia";
import { useVideoUploadStore } from "@/store/video_upload";
import { useUserStore } from "@/store/user";
import { useVideoStore } from "@/store/video";

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
      tab: null,
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
      var extensions = [" B", " kB", " MB", " GB"];
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
    ...mapStores(useVideoUploadStore, useUserStore, useVideoStore),
  },
  methods: {
    validateFile(file) {
      if (!file) {
        this.file_valid = false;
        return "Please select a file.";
      }
      if (file.size > this.max_size) {
        this.file_valid = false;
        return (
          "File exceeds your maximum file size of " + this.max_size_in_words
        );
      }
      if (!file.name.endsWith(".mp4")) {
        this.file_valid = false;
        return "File is not in the .mp4 format.";
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
