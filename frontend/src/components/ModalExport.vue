<template>
  <v-dialog v-model="dialog" max-width="90%">
    <v-card>
      <v-card-title class="mb-2">
        {{ $t("modal.export.title") }}

        <v-btn icon @click="dialog = false" absolute right>
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text>
        <v-tabs vertical class="tabs-left">
          <v-tab v-for="export_format in export_formats_sorted" :key="export_format.name">
            <v-icon left> {{ export_format.icon }} </v-icon>
            <span class="text-button">{{ export_format.name }}</span>
          </v-tab>
          <v-tab-item v-for="export_format in export_formats_sorted" :key="export_format.name">
            <v-card flat height="100%">
              <v-card-title>{{ export_format.name }} </v-card-title>
              <v-card-text>
                <Parameters :videoIds="[videoId]" :parameters="export_format.parameters">
                </Parameters>
              </v-card-text>

              <v-card-actions class="pt-0">
                <v-btn @click="
                  downloadExport(
                    export_format.export,
                    export_format.parameters
                  )
                  ">{{ $t("modal.export.export") }}</v-btn>
              </v-card-actions>
            </v-card>
          </v-tab-item>
        </v-tabs>
      </v-card-text>
      <v-card-actions class="pt-0">
        <v-btn @click="dialog = false">{{ $t("modal.export.close") }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script>
import Parameters from "./Parameters.vue";
import { mapStores } from "pinia";
import { useVideoStore } from "@/store/video";
import { usePlayerStore } from "@/store/player";

export default {
  props: ["value"],
  data() {
    return {
      dialog: false,
      export_formats: [
        {
          name: this.$t("modal.export.merged_csv.export_name"),
          icon: "mdi-file",
          export: "merged_csv",
          parameters: [
            {
              field: "checkbox",
              name: "merge_timeline",
              value: true,
              text: this.$t("modal.export.merged_csv.timeline_merge"),
            },
            {
              field: "checkbox",
              name: "use_timestamps",
              value: true,
              text: this.$t("modal.export.merged_csv.use_timestamps"),
            },
            {
              field: "checkbox",
              name: "use_seconds",
              value: true,
              text: this.$t("modal.export.merged_csv.use_seconds"),
            },
            {
              field: "checkbox",
              name: "include_category",
              value: true,
              text: this.$t("modal.export.merged_csv.include_category"),
            },
            {
              field: "checkbox",
              name: "split_places",
              value: true,
              text: this.$t("modal.export.merged_csv.split_places"),
            },
          ],
        },
        {
          name: this.$t("modal.export.individual_csv.export_name"),
          icon: "mdi-file",
          export: "individual_csv",
          parameters: [
            {
              field: "checkbox",
              name: "use_timestamps",
              value: true,
              text: this.$t("modal.export.individual_csv.use_timestamps"),
            },
            {
              field: "checkbox",
              name: "use_seconds",
              value: true,
              text: this.$t("modal.export.individual_csv.use_seconds"),
            },
            {
              field: "checkbox",
              name: "include_category",
              value: true,
              text: this.$t("modal.export.individual_csv.include_category"),
            },
          ],
        },
        {
          name: this.$t("modal.export.elan.export_name"),
          icon: "mdi-file",
          export: "elan",
          parameters: [
            {
              field: "select_timeline",
              name: "shot_timeline_id",
              text: this.$t("modal.plugin.shot_timeline_name"),
              hint: this.$t("modal.plugin.shot_timeline_hint"),
            },
            {
              field: "buttongroup",
              text: this.$t("modal.plugin.aggregation.method"),
              name: "aggregation",
              value: 0,
              buttons: [
                this.$t("modal.plugin.aggregation.max"),
                this.$t("modal.plugin.aggregation.min"),
                this.$t("modal.plugin.aggregation.mean"),
              ],
            },
          ],
        },
      ],
    };
  },
  computed: {
    videoId() {
      return this.playerStore.videoId;
    },
    export_formats_sorted() {
      return this.export_formats.slice(0).sort((a, b) => a.name.localeCompare(b.name));
    },
    ...mapStores(useVideoStore, usePlayerStore),
  },
  methods: {
    async downloadExport(format, parameters) {
      parameters = parameters.map((e) => {
        if ("file" in e) {
          return { name: e.name, file: e.file };
        } else if (e.name === "shot_timeline_id") {
          return { name: e.name, value: e.value.timeline_ids[0] };
        } else {
          return { name: e.name, value: e.value };
        }
      });
      this.videoStore
        .export({ format: format, parameters: parameters })
        .then(() => {
          this.dialog = false;
        });
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
