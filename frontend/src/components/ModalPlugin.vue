<template>
  <v-dialog
    v-model="dialog"
    max-width="90%"
    min-width="600px"
    :fullscreen="$vuetify.breakpoint.xsOnly"
  >
    <template v-slot:activator="{ on, attrs }">
      <slot name="activator" :on="on" :attrs="attrs">
        <v-btn tile text v-bind="attrs" v-on="on">
          <v-icon>{{ "mdi-plus" }}</v-icon>
          {{ $t("modal.plugin.link") }}
        </v-btn>
      </slot>
    </template>

    <v-card height="80vh" class="d-flex flex-column">
      <v-card-title>
        {{ $t("modal.plugin.title") }}

        <v-btn icon @click.native="dialog = false" absolute top right>
          <v-icon>mdi-close</v-icon>
        </v-btn>

        <v-tabs v-model="tab" fixed-tabs>
          <v-tabs-slider></v-tabs-slider>

          <v-tab> {{ $t("modal.plugin.tab_legal") }} </v-tab>
          <v-tab :disabled="!checkbox">
            {{ $t("modal.plugin.tab_plugin") }}
          </v-tab>
        </v-tabs>
      </v-card-title>
      <v-card-text style="overflow-y: scroll">
        <v-tabs-items v-model="tab">
          <v-tab-item class="scroll">
            <h1 class="mt-2">{{ $t("terms.title") }}</h1>
            <p v-html="$t('terms.content')"></p>
            <v-form class="terms-input">
              <v-checkbox
                v-model="checkbox"
                label="Do you agree with the terms of services?"
                required
              >
              </v-checkbox>
            </v-form>
          </v-tab-item>
          <v-tab-item style="height: 100%">
            <v-row style="height: 100%">
              <v-col
                cols="3"
                style="height: 100%; display: flex; flex-direction: column"
              >
                <v-sheet
                  class="pa-1"
                  style="background-color: rgb(174, 19, 19) !important"
                >
                  <v-text-field
                    v-model="search"
                    label="Search Plugin"
                    class="searchField"
                    dark
                    flat
                    solo-inverted
                    hide-details
                    clearable
                    clear-icon="mdi-close-circle-outline"
                  >
                  </v-text-field>
                </v-sheet>
                <v-treeview
                  :items="plugins_sorted"
                  :search="search"
                  :open.sync="open"
                  activatable
                  open-all
                  style="cursor: pointer; overflow-y: scroll"
                  :active.sync="active"
                >
                  <template v-slot:prepend="{ item }">
                    <v-icon>{{ item.icon }}</v-icon>
                  </template>
                </v-treeview>
              </v-col>
              <v-col
                cols="9"
                style="height: 100%; display: flex; flex-direction: column"
              >
                <div
                  v-if="!selected"
                  class="text-h6 grey--text font-weight-light"
                  style="text-align: center"
                >
                  {{ $t("modal.plugin.search.select") }}
                </div>
                <v-card
                  v-else
                  :key="selected.id"
                  class="mx-auto overflow-y-auto"
                  style="height: 100%"
                  flat
                >
                  <v-card-title class="mb-0">
                    {{ selected.name }}
                  </v-card-title>
                  <v-card-text>
                    <div
                      style="padding-bottom: 2em"
                      v-html="selected.description"
                    ></div>
                    <Parameters
                      :parameters="selected.parameters"
                      :videoIds="videoIds"
                    >
                    </Parameters>
                    <v-expansion-panels
                      v-if="
                        selected.optional_parameters &&
                        selected.optional_parameters.length > 0
                      "
                    >
                      <v-expansion-panel>
                        <v-expansion-panel-header expand-icon="mdi-menu-down">
                          Advanced Options
                        </v-expansion-panel-header>

                        <v-expansion-panel-content>
                          <Parameters
                            :parameters="selected.optional_parameters"
                            :videoIds="videoIds"
                          >
                          </Parameters>
                        </v-expansion-panel-content>
                      </v-expansion-panel>
                    </v-expansion-panels>
                  </v-card-text>
                  <v-card-actions class="pt-0"> </v-card-actions>
                </v-card>
              </v-col>
            </v-row>
          </v-tab-item>
        </v-tabs-items>
      </v-card-text>

      <v-spacer></v-spacer>
      <v-card-actions class="pt-0">
        <v-btn
          v-if="tab == 0"
          class="mr-4"
          :disabled="!checkbox"
          @click="tab++"
        >
          {{ $t("modal.plugin.continue") }}
        </v-btn>
        <v-btn
          v-if="tab == 1"
          :disabled="!selected"
          @click="
            runPlugin(
              selected.plugin,
              selected.parameters,
              selected.optional_parameters
            )
          "
          >{{ $t("modal.plugin.run") }}</v-btn
        >
        <v-btn @click="dialog = false">{{ $t("modal.plugin.close") }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script>
import { mapStores } from "pinia";
import { usePluginRunStore } from "@/store/plugin_run";
import Parameters from "./Parameters.vue";
// import { useTimelineStore } from "../store/timeline";

export default {
  props: ["value", "videoIds"],
  data() {
    return {
      dialog: false,
      checkbox: false,
      tab: null,
      open: [1, 2],
      search: null,
      active: [],
      plugins: [
        {
          id: 1,
          name: this.$t("modal.plugin.groups.audio"),
          children: [
            {
              name: this.$t("modal.plugin.audio_rms.plugin_name"),
              description: this.$t("modal.plugin.audio_rms.plugin_description"),
              icon: "mdi-waveform",
              plugin: "audio_rms",
              id: 101,
              parameters: [
                {
                  field: "text_field",
                  name: "timeline",
                  value: this.$t("modal.plugin.audio_rms.timeline_name"),
                  text: this.$t("modal.plugin.timeline_name"),
                },
              ],
              optional_parameters: [
                {
                  field: "slider",
                  min: 1000,
                  max: 24000,
                  value: 8000,
                  step: 1000,
                  name: "sr",
                  text: this.$t("modal.plugin.audio_waveform.sr"),
                },
              ],
            },
            {
              name: this.$t("modal.plugin.audio_frequency.plugin_name"),
              description: this.$t(
                "modal.plugin.audio_frequency.plugin_description"
              ),
              icon: "mdi-waveform",
              plugin: "audio_freq",
              id: 102,
              parameters: [
                {
                  field: "text_field",
                  name: "timeline",
                  value: this.$t("modal.plugin.audio_frequency.timeline_name"),
                  text: this.$t("modal.plugin.timeline_name"),
                },
              ],
              optional_parameters: [
                {
                  field: "slider",
                  min: 1000,
                  max: 24000,
                  value: 8000,
                  step: 1000,
                  name: "sr",
                  text: this.$t("modal.plugin.audio_frequency.sr"),
                },
                {
                  field: "slider",
                  min: 64,
                  max: 512,
                  value: 256,
                  step: 64, // TODO: only valid for values with power of 2
                  name: "n_fft",
                  text: this.$t("modal.plugin.audio_frequency.n_fft"),
                },
              ],
            },
            {
              name: this.$t("modal.plugin.audio_waveform.plugin_name"),
              description: this.$t(
                "modal.plugin.audio_waveform.plugin_description"
              ),
              icon: "mdi-waveform",
              plugin: "audio_amp",
              id: 103,
              parameters: [
                {
                  field: "text_field",
                  name: "timeline",
                  value: this.$t("modal.plugin.audio_waveform.timeline_name"),
                  text: this.$t("modal.plugin.timeline_name"),
                },
              ],
              optional_parameters: [
                {
                  field: "slider",
                  min: 1000,
                  max: 24000,
                  value: 8000,
                  step: 1000,
                  name: "sr",
                  text: this.$t("modal.plugin.audio_waveform.sr"),
                },
              ],
            },
            {
              name: this.$t("modal.plugin.whisper.plugin_name"),
              description: this.$t("modal.plugin.whisper.plugin_description"),
              icon: "mdi-waveform",
              plugin: "whisper",
              id: 104,
              parameters: [],
              optional_parameters: [],
            },
          ],
        },
        {
          id: 2,
          name: this.$t("modal.plugin.groups.face"),
          children: [
            {
              name: this.$t("modal.plugin.face_clustering.plugin_name"),
              description: this.$t(
                "modal.plugin.face_clustering.plugin_description"
              ),
              icon: "mdi-ungroup",
              plugin: "face_clustering",
              id: 201,
              parameters: [
                {
                  field: "slider",
                  min: 0.3,
                  max: 0.7,
                  value: 0.5,
                  step: 0.01,
                  name: "cluster_threshold",
                  hint_right: this.$t(
                    "modal.plugin.face_clustering.threshold.hint_right"
                  ),
                  hint_left: this.$t(
                    "modal.plugin.face_clustering.threshold.hint_left"
                  ),
                },
                {
                  field: "slider",
                  min: 1,
                  max: 100,
                  value: 50,
                  step: 1,
                  name: "max_cluster",
                  hint_right: this.$t(
                    "modal.plugin.face_clustering.max_cluster.hint_right"
                  ),
                  hint_left: this.$t(
                    "modal.plugin.face_clustering.max_cluster.hint_left"
                  ),
                },
                {
                  field: "slider",
                  min: 1,
                  max: 100,
                  value: 20,
                  step: 1,
                  name: "max_samples_per_cluster",
                  hint_right: this.$t(
                    "modal.plugin.face_clustering.max_faces.hint_right"
                  ),
                  hint_left: this.$t(
                    "modal.plugin.face_clustering.max_faces.hint_left"
                  ),
                },
                {
                  field: "slider",
                  min: 0,
                  max: 1.0,
                  value: 0.1,
                  step: 0.05,
                  name: "min_face_height",
                  hint_right: this.$t(
                    "modal.plugin.face_clustering.min_face_height.hint_right"
                  ),
                  hint_left: this.$t(
                    "modal.plugin.face_clustering.min_face_height.hint_left"
                  ),
                },
              ],
              optional_parameters: [
                {
                  field: "select_options",
                  text: this.$t(
                    "modal.plugin.face_clustering.clustering_method_name"
                  ),
                  hint: this.$t(
                    "modal.plugin.face_clustering.clustering_method_hint"
                  ),
                  items: ["Agglomerative", "DBScan"],
                  name: "clustering_method",
                  value: "DBScan",
                },
                {
                  field: "slider",
                  min: 1,
                  max: 10,
                  value: 2,
                  step: 1,
                  name: "fps",
                  text: this.$t("modal.plugin.fps"),
                },
              ],
            },
            {
              name: this.$t("modal.plugin.face_identification.plugin_name"),
              description: this.$t(
                "modal.plugin.face_identification.plugin_description"
              ),
              icon: "mdi-account-search",
              plugin: "insightface_identification",
              id: 202,
              parameters: [
                {
                  field: "text_field",
                  name: "timeline",
                  value: this.$t(
                    "modal.plugin.face_identification.timeline_name"
                  ),
                  text: this.$t("modal.plugin.timeline_name"),
                },
                {
                  field: "image_input",
                  file: null,
                  name: "query_images",
                  text: this.$t(
                    "modal.plugin.face_identification.query_images"
                  ),
                  hint: this.$t(
                    "modal.plugin.face_identification.query_images_hint"
                  ),
                },
              ],
              optional_parameters: [
                {
                  field: "slider",
                  min: 1,
                  max: 10,
                  value: 2,
                  step: 1,
                  name: "fps",
                  text: this.$t("modal.plugin.fps"),
                },
              ],
            },
            {
              name: this.$t("modal.plugin.faceemotion.plugin_name"),
              description: this.$t(
                "modal.plugin.faceemotion.plugin_description"
              ),
              icon: "mdi-emoticon-happy-outline",
              plugin: "deepface_emotion",
              id: 203,
              parameters: [
                {
                  field: "text_field",
                  name: "timeline",
                  value: this.$t("modal.plugin.faceemotion.timeline_name"),
                  text: this.$t("modal.plugin.timeline_name"),
                },
                {
                  field: "select_timeline",
                  name: "shot_timeline_id",
                  // value: this.shot_timelines_names[0],
                  // items: this.shot_timelines_names,
                  text: this.$t("modal.plugin.shot_timeline_name"),
                  hint: this.$t("modal.plugin.shot_timeline_hint"),
                },
              ],
              optional_parameters: [
                {
                  field: "slider",
                  min: 1,
                  max: 10,
                  value: 2,
                  step: 1,
                  name: "fps",
                  text: this.$t("modal.plugin.fps"),
                },
                {
                  field: "slider",
                  min: 24,
                  max: 256,
                  value: 48,
                  step: 8,
                  name: "min_facesize",
                  text: this.$t("modal.plugin.faceemotion.min_facesize"),
                  disabled: true,
                },
              ],
            },
            // {
            //   name: this.$t("modal.plugin.facesize.plugin_name"),
            //   icon: "mdi-face-recognition",
            //   plugin: "insightface_facesize",
            //   id: 204,
            //   parameters: [
            //     {
            //       field: "text_field",
            //       name: "timeline",
            //       value: this.$t("modal.plugin.facesize.timeline_name"),
            //       text: this.$t("modal.plugin.timeline_name"),
            //     },
            //     {
            //       field: "select_timeline",
            //       name: "shot_timeline_id",
            //       // value: this.shot_timelines_names[0],
            //       // items: this.shot_timelines_names,
            //       text: this.$t("modal.plugin.shot_timeline_name"),
            //       hint: this.$t("modal.plugin.shot_timeline_hint"),
            //     },
            //   ],
            //   optional_parameters: [
            //     {
            //       field: "slider",
            //       min: 1,
            //       max: 10,
            //       value: 2,
            //       step: 1,
            //       name: "fps",
            //       text: this.$t("modal.plugin.fps"),
            //     },
            //   ],
            // },
          ],
        },
        {
          id: 3,
          name: this.$t("modal.plugin.groups.color"),
          children: [
            {
              name: this.$t("modal.plugin.color_analysis.plugin_name"),
              description: this.$t(
                "modal.plugin.color_analysis.plugin_description"
              ),
              icon: "mdi-palette",
              plugin: "color_analysis",
              id: 301,
              parameters: [
                {
                  field: "text_field",
                  name: "timeline",
                  value: this.$t("modal.plugin.color_analysis.timeline_name"),
                  text: this.$t("modal.plugin.timeline_name"),
                },
                {
                  field: "slider",
                  min: 1,
                  max: 8,
                  value: 1,
                  step: 1,
                  name: "k",
                  text: this.$t("modal.plugin.color_analysis.slider"),
                },
              ],
              optional_parameters: [
                {
                  field: "slider",
                  min: 1,
                  max: 10,
                  value: 2,
                  step: 1,
                  name: "fps",
                  text: this.$t("modal.plugin.fps"),
                },
                {
                  field: "slider",
                  min: 24,
                  max: 128,
                  value: 48,
                  step: 4,
                  name: "max_resolution",
                  text: this.$t("modal.plugin.color_analysis.max_resolution"),
                },
                {
                  field: "slider",
                  min: 5,
                  max: 25,
                  value: 10,
                  step: 5,
                  name: "max_iter",
                  text: this.$t("modal.plugin.color_analysis.max_iter"),
                },
              ],
            },
            {
              name: this.$t(
                "modal.plugin.color_brightness_analysis.plugin_name"
              ),
              description: this.$t(
                "modal.plugin.color_brightness_analysis.plugin_description"
              ),
              icon: "mdi-palette",
              plugin: "color_brightness_analysis",
              id: 302,
              parameters: [
                {
                  field: "text_field",
                  name: "timeline",
                  value: this.$t(
                    "modal.plugin.color_brightness_analysis.timeline_name"
                  ),
                  text: this.$t("modal.plugin.timeline_name"),
                },
              ],
              optional_parameters: [
                {
                  field: "slider",
                  min: 1,
                  max: 10,
                  value: 2,
                  step: 1,
                  name: "fps",
                  text: this.$t("modal.plugin.fps"),
                },
                {
                  field: "checkbox",
                  name: "normalize",
                  text: this.$t("modal.plugin.normalize"),
                  value: true,
                },
              ],
            },
          ],
        },
        {
          id: 4,
          name: this.$t("modal.plugin.groups.identification"),
          children: [
            {
              name: this.$t("modal.plugin.clip.plugin_name"),
              description: this.$t("modal.plugin.clip.plugin_description"),
              icon: "mdi-eye",
              plugin: "clip",
              id: 403,
              parameters: [
                {
                  field: "text_field",
                  name: "timeline",
                  value: this.$t("modal.plugin.clip.timeline_name"),
                  text: this.$t("modal.plugin.timeline_name"),
                },
                {
                  field: "text_field",
                  name: "search_term",
                  value: "",
                  text: this.$t("modal.plugin.clip.search_term"),
                },
              ],
              optional_parameters: [
                {
                  field: "slider",
                  min: 1,
                  max: 10,
                  value: 2,
                  step: 1,
                  name: "fps",
                  text: this.$t("modal.plugin.fps"),
                },
              ],
            },
            {
              name: this.$t("modal.plugin.clip_ontology.plugin_name"),
              description: this.$t(
                "modal.plugin.clip_ontology.plugin_description"
              ),
              icon: "mdi-eye",
              plugin: "clip_ontology",
              id: 402,
              parameters: [
                {
                  field: "text_field",
                  name: "timeline",
                  value: this.$t("modal.plugin.clip_ontology.timeline_name"),
                  text: this.$t("modal.plugin.timeline_name"),
                },
                {
                  field: "select_timeline",
                  name: "shot_timeline_id",
                  // value: this.shot_timelines_names[0],
                  // items: this.shot_timelines_names,
                  text: this.$t("modal.plugin.shot_timeline_name"),
                  hint: this.$t("modal.plugin.shot_timeline_hint"),
                },
                {
                  field: "csv_input",
                  file: null,
                  name: "concept_csv",
                  text: this.$t("modal.plugin.clip_ontology.concepts"),
                  hint: this.$t("modal.plugin.clip_ontology.concepts_hint"),
                },
              ],
              optional_parameters: [
                {
                  field: "slider",
                  min: 1,
                  max: 10,
                  value: 2,
                  step: 1,
                  name: "fps",
                  text: this.$t("modal.plugin.fps"),
                },
              ],
            },
            {
              name: this.$t("modal.plugin.x_clip.plugin_name"),
              description: this.$t("modal.plugin.x_clip.plugin_description"),
              icon: "mdi-eye",
              plugin: "x_clip",
              id: 404,
              parameters: [
                {
                  field: "text_field",
                  name: "timeline",
                  value: this.$t("modal.plugin.x_clip.timeline_name"),
                  text: this.$t("modal.plugin.timeline_name"),
                },
                {
                  field: "text_field",
                  name: "search_term",
                  value: "",
                  text: this.$t("modal.plugin.x_clip.search_term"),
                },
              ],
              optional_parameters: [
                {
                  field: "slider",
                  min: 1,
                  max: 10,
                  value: 2,
                  step: 1,
                  name: "fps",
                  text: this.$t("modal.plugin.fps"),
                },
              ],
            },
            {
              name: this.$t("modal.plugin.places_classification.plugin_name"),
              description: this.$t(
                "modal.plugin.places_classification.plugin_description"
              ),
              icon: "mdi-map-marker",
              plugin: "places_classification",
              id: 401,
              parameters: [
                {
                  field: "text_field",
                  name: "timeline",
                  value: this.$t(
                    "modal.plugin.places_classification.timeline_name"
                  ),
                  text: this.$t("modal.plugin.timeline_name"),
                },
                {
                  field: "select_timeline",
                  name: "shot_timeline_id",
                  // value: this.shot_timelines_names[0],
                  // items: this.shot_timelines_names,
                  text: this.$t("modal.plugin.shot_timeline_name"),
                  hint: this.$t("modal.plugin.shot_timeline_hint"),
                },
              ],
              optional_parameters: [
                {
                  field: "slider",
                  min: 1,
                  max: 10,
                  value: 2,
                  step: 1,
                  name: "fps",
                  text: this.$t("modal.plugin.fps"),
                },
              ],
            },
            {
              name: this.$t("modal.plugin.place_clustering.plugin_name"),
              description: this.$t(
                "modal.plugin.place_clustering.plugin_description"
              ),
              icon: "mdi-ungroup",
              plugin: "place_clustering",
              id: 405,
              parameters: [
                {
                  field: "select_timeline",
                  name: "shot_timeline_id",
                  text: this.$t("modal.plugin.shot_timeline_name"),
                  hint: this.$t("modal.plugin.shot_timeline_hint"),
                },
                //                {
                //                  field: "select_options",
                //                  text: this.$t("modal.plugin.place_clustering.encoder_name"),
                //                  hint: this.$t("modal.plugin.place_clustering.encoder_hint"),
                //                  items: ["CLIP", "Places"],
                //                  name: "encoder",
                //                },
                {
                  field: "slider",
                  min: 0.05,
                  max: 0.3,
                  value: 0.15,
                  step: 0.01,
                  name: "cluster_threshold",
                  hint_right: this.$t(
                    "modal.plugin.place_clustering.threshold.hint_right"
                  ),
                  hint_left: this.$t(
                    "modal.plugin.place_clustering.threshold.hint_left"
                  ),
                },
                {
                  field: "slider",
                  min: 1,
                  max: 100,
                  value: 50,
                  step: 1,
                  name: "max_cluster",
                  hint_right: this.$t(
                    "modal.plugin.place_clustering.max_cluster.hint_right"
                  ),
                  hint_left: this.$t(
                    "modal.plugin.place_clustering.max_cluster.hint_left"
                  ),
                },
              ],
              optional_parameters: [
                {
                  field: "select_options",
                  text: this.$t(
                    "modal.plugin.place_clustering.clustering_method_name"
                  ),
                  hint: this.$t(
                    "modal.plugin.place_clustering.clustering_method_hint"
                  ),
                  items: ["Agglomerative", "DBScan"],
                  name: "clustering_method",
                  value: "DBScan",
                },
              ],
            },
            {
              name: this.$t("modal.plugin.blip.plugin_name"),
              description: this.$t("modal.plugin.blip.plugin_description"),
              icon: "mdi-eye",
              plugin: "blip_vqa",
              id: 406,
              parameters: [
                {
                  field: "text_field",
                  name: "timeline",
                  value: this.$t("modal.plugin.blip.timeline_name"),
                  text: this.$t("modal.plugin.timeline_name"),
                },
                {
                  field: "select_timeline",
                  name: "shot_timeline_id",
                  // value: this.shot_timelines_names[0],
                  // items: this.shot_timelines_names,
                  text: this.$t("modal.plugin.shot_timeline_name"),
                  hint: this.$t("modal.plugin.shot_timeline_hint"),
                },
                {
                  field: "text_field",
                  name: "query_term",
                  value: "",
                  text: this.$t("modal.plugin.blip.search_term"),
                },
              ],
              optional_parameters: [],
            },
            {
              name: this.$t("modal.plugin.ocr.plugin_name"),
              icon: "mdi-text-shadow",
              plugin: "ocr_video_detector_onnx",
              id: 407,
              parameters: [
                {
                  field: "text_field",
                  name: "timeline",
                  value: this.$t("modal.plugin.ocr.timeline_name"),
                  text: this.$t("modal.plugin.ocr.timeline_name"),
                },
                {
                  field: "text_field",
                  name: "search_term",
                  value: "",
                  text: this.$t("modal.plugin.ocr.search_term"),
                },
              ],
              optional_parameters: [
                {
                  field: "slider",
                  min: 1,
                  max: 10,
                  value: 2,
                  step: 1,
                  name: "fps",
                  text: this.$t("modal.plugin.fps"),
                },
              ],
            },
            {
              name: this.$t("modal.plugin.nano_ocr.plugin_name"),
              icon: "mdi-text-shadow",
              plugin: "nano_ocr_video",
              id: 408,
              parameters: [
                {
                  field: "text_field",
                  name: "timeline",
                  value: this.$t("modal.plugin.ocr.timeline_name"),
                  text: this.$t("modal.plugin.ocr.timeline_name"),
                },
              ],
              optional_parameters: [
                {
                  field: "slider",
                  min: 1,
                  max: 1,
                  value: 1,
                  step: 1,
                  name: "fps",
                  text: this.$t("modal.plugin.fps"),
                },
              ],
            },
          ],
        },
        {
          id: 5,
          name: this.$t("modal.plugin.groups.shot"),
          children: [
            {
              name: this.$t("modal.plugin.shot_detection.plugin_name"),
              description: this.$t(
                "modal.plugin.shot_detection.plugin_description"
              ),
              icon: "mdi-arrow-expand-horizontal",
              plugin: "shotdetection",
              id: 501,
              parameters: [
                {
                  field: "text_field",
                  name: "timeline",
                  value: this.$t("modal.plugin.shot_detection.timeline_name"),
                  text: this.$t("modal.plugin.timeline_name"),
                },
              ],
              optional_parameters: [
                {
                  field: "slider",
                  min: 1,
                  max: 10,
                  value: 2,
                  step: 1,
                  name: "fps",
                  text: this.$t("modal.plugin.fps"),
                },
              ],
            },
            {
              name: this.$t("modal.plugin.shot_density.plugin_name"),
              description: this.$t(
                "modal.plugin.shot_density.plugin_description"
              ),
              icon: "mdi-sine-wave",
              plugin: "shot_density",
              id: 503,
              parameters: [
                {
                  field: "text_field",
                  name: "timeline",
                  value: this.$t("modal.plugin.shot_density.timeline_name"),
                  text: this.$t("modal.plugin.timeline_name"),
                },
                {
                  field: "select_timeline",
                  name: "shot_timeline_id",
                  text: this.$t("modal.plugin.shot_density.input_timeline"),
                },
              ],
              optional_parameters: [
                {
                  field: "slider",
                  min: 1,
                  max: 60,
                  value: 10,
                  step: 1,
                  name: "bandwidth",
                  text: this.$t("modal.plugin.shot_density.bandwidth"),
                },
                {
                  field: "slider",
                  min: 1,
                  max: 10,
                  value: 10,
                  step: 1,
                  name: "fps",
                  text: this.$t("modal.plugin.fps"),
                },
              ],
            },
            {
              name: this.$t(
                "modal.plugin.shot_type_classification.plugin_name"
              ),
              description: this.$t(
                "modal.plugin.shot_type_classification.plugin_description"
              ),
              icon: "mdi-video-switch",
              plugin: "shot_type_classification",
              id: 504,
              parameters: [
                {
                  field: "text_field",
                  name: "timeline",
                  value: this.$t(
                    "modal.plugin.shot_type_classification.timeline_name"
                  ),
                  text: this.$t("modal.plugin.timeline_name"),
                },
                {
                  field: "select_timeline",
                  name: "shot_timeline_id",
                  text: this.$t("modal.plugin.shot_timeline_name"),
                  hint: this.$t("modal.plugin.shot_timeline_hint"),
                },
              ],
              optional_parameters: [
                {
                  field: "slider",
                  min: 1,
                  max: 10,
                  value: 2,
                  step: 1,
                  name: "fps",
                  text: this.$t("modal.plugin.fps"),
                },
              ],
            },
            {
              name: this.$t("modal.plugin.shot_scalar_annotation.plugin_name"),
              description: this.$t(
                "modal.plugin.shot_scalar_annotation.plugin_description"
              ),
              icon: "mdi-label-outline",
              plugin: "shot_scalar_annotation",
              id: 505,
              parameters: [
                {
                  field: "text_field",
                  name: "timeline",
                  value: this.$t(
                    "modal.plugin.shot_scalar_annotation.timeline_name"
                  ),
                  text: this.$t("modal.plugin.timeline_name"),
                },
                {
                  field: "select_timeline",
                  name: "shot_timeline_id",
                  text: this.$t("modal.plugin.shot_timeline_name"),
                  hint: this.$t("modal.plugin.shot_timeline_hint"),
                },
                {
                  field: "select_scalar_timeline",
                  name: "scalar_timeline_id",
                  text: this.$t("modal.plugin.scalar_timeline_name"),
                  hint: this.$t("modal.plugin.scalar_timeline_hint"),
                },
              ],
              optional_parameters: [],
            },
            {
              name: this.$t("modal.plugin.thumbnail.plugin_name"),
              description: this.$t("modal.plugin.thumbnail.plugin_description"),
              icon: "mdi-image-multiple",
              plugin: "thumbnail",
              id: 502,
              parameters: [],
              optional_parameters: [],
            },
          ],
        },
        {
          id: 6,
          name: this.$t("modal.plugin.groups.aggregation"),
          children: [
            {
              name: this.$t("modal.plugin.aggregation.plugin_name"),
              description: this.$t(
                "modal.plugin.aggregation.plugin_description"
              ),
              icon: "mdi-sigma",
              plugin: "aggregate_scalar",
              id: 601,
              parameters: [
                {
                  field: "text_field",
                  name: "timeline",
                  value: this.$t("modal.plugin.aggregation.timeline_name"),
                  text: this.$t("modal.plugin.timeline_name"),
                },
                {
                  field: "select_scalar_timelines",
                  name: "timeline_ids",
                  text: this.$t("modal.plugin.scalar_timeline_name"),
                  hint: this.$t("modal.plugin.scalar_timeline_hint"),
                },
                {
                  field: "buttongroup",
                  text: this.$t("modal.plugin.aggregation.method"),
                  name: "aggregation",
                  value: 0,
                  buttons: [
                    this.$t("modal.plugin.aggregation.logical_or"),
                    this.$t("modal.plugin.aggregation.logical_and"),
                    this.$t("modal.plugin.aggregation.mean"),
                    this.$t("modal.plugin.aggregation.prod"),
                  ],
                },
              ],
              optional_parameters: [],
            },
            {
              name: this.$t("modal.plugin.invert.plugin_name"),
              description: this.$t("modal.plugin.invert.plugin_description"),
              icon: "mdi-numeric-negative-1",
              plugin: "invert_scalar",
              id: 602,
              parameters: [
                {
                  field: "text_field",
                  name: "timeline",
                  value: this.$t("modal.plugin.invert.timeline_name"),
                  text: this.$t("modal.plugin.timeline_name"),
                },
                {
                  field: "select_scalar_timeline",
                  name: "scalar_timeline_id",
                  text: this.$t("modal.plugin.scalar_timeline_name"),
                  hint: this.$t("modal.plugin.scalar_timeline_hint"),
                },
              ],
              optional_parameters: [],
            },
          ],
        },
      ],
    };
  },
  computed: {
    plugins_sorted() {
      return this.plugins.slice(0).sort((a, b) => a.name.localeCompare(b.name));
    },
    selected() {
      if (!this.active.length) return undefined;

      const id = this.active[0];
      if (id < 100) return undefined;

      let plugin_group = this.plugins.find(
        (group) => group.id === parseInt(id / 100)
      );
      let plugin = plugin_group.children.find((plugin) => plugin.id === id);

      return plugin;
    },
    filter() {
      return (item, search, textKey) => item[textKey].indexOf(search) > -1;
    },
    ...mapStores(usePluginRunStore),
  },
  methods: {
    async runPlugin(plugin, parameters, optional_parameters) {
      parameters = parameters.concat(optional_parameters);
      parameters = parameters.map((e) => {
        if ("file" in e) {
          return { name: e.name, file: e.file };
        } else {
          return { name: e.name, value: e.value };
        }
      });
      for (const video of this.videoIds) {
        const video_params = [];
        // if multiple videos were selected, choose the correct timeline in parameters
        for (const param of parameters) {
          if (
            param.name === "shot_timeline_id" ||
            param.name == "scalar_timeline_id"
          ) {
            video_params.push({
              name: param.name,
              value:
                param.value.timeline_ids[param.value.video_ids.indexOf(video)],
            });
          } else if (param.name === "timeline_ids") {
            video_params.push({
              name: param.name,
              value: param.value.map(
                (t) => t.timeline_ids[t.video_ids.indexOf(video)]
              ),
            });
          } else {
            video_params.push(param);
          }
        }
        this.pluginRunStore
          .submit({ plugin: plugin, parameters: video_params, videoId: video })
          .then(() => {
            this.dialog = false;
          });
      }
    },
  },
  watch: {
    dialog(value) {
      this.$emit("input", value);
    },
    value(value) {
      if (value) {
        this.dialog = true;
      }
    },
  },
  components: { Parameters },
};
</script>

<style>
div.tabs-left [role="tab"] {
  justify-content: flex-start;
}

.scroll {
  overflow-y: scroll;
}

.terms-input {
  margin-bottom: 10px;
  margin-left: 10px;
}
</style>
