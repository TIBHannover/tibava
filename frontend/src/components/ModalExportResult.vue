<template>
  <v-dialog v-model="dialog" max-width="1000">
    <template v-slot:activator="{ on }">
      <v-btn v-on="on" text block large>
        <v-icon left>mdi-swap-vertical</v-icon>
        {{ $t("modal.timeline.export_result.link") }}
      </v-btn>
    </template>
    <v-card>
      <v-card-title class="mb-2">
        {{ $t("modal.timeline.export_result.title") }}

        <v-btn icon @click.native="dialog = false" absolute top right>
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text>
        <v-tabs vertical class="tabs-left">
          <v-tab
            v-for="export_format in export_formats_sorted"
            :key="export_format.name"
          >
            <v-icon left> {{ export_format.icon }} </v-icon>
            <span class="text-button">{{ export_format.name }}</span>
          </v-tab>
          <v-tab-item
            v-for="export_format in export_formats_sorted"
            :key="export_format.name"
          >
            <v-card flat height="100%">
              <v-card-title>{{ export_format.name }} </v-card-title>
              <v-card-text>
                <Parameters :parameters="export_format.parameters">
                </Parameters>
              </v-card-text>

              <v-card-actions class="pt-0">
                <v-btn
                  @click="
                    downloadExport(
                      export_format.export,
                      export_format.parameters
                    )
                  "
                  >{{ $t("modal.timeline.export_result.export") }}</v-btn
                >
              </v-card-actions>
            </v-card>
          </v-tab-item>
        </v-tabs>
      </v-card-text>
      <v-card-actions class="pt-0">
        <v-btn @click="dialog = false">{{
          $t("modal.timeline.export_result.close")
        }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script>
import Parameters from "./Parameters.vue";
import { mapStores } from "pinia";
import { useTimelineStore } from "@/store/timeline";
import { usePluginRunResultStore } from "@/store/plugin_run_result";

export default {
  props: ["value", "timeline"],
  data() {
    return {
      dialog: false,
      export_formats: [
        {
          name: this.$t("modal.timeline.export_result.csv.export_name"),
          icon: "mdi-file",
          export: "csv",
          parameters: [
            // {
            //   field: "checkbox",
            //   name: "merge_timeline",
            //   value: true,
            //   text: this.$t("modal.timeline.export_result.csv.timeline_merge"),
            // },
            // {
            //   field: "checkbox",
            //   name: "use_timestamps",
            //   value: true,
            //   text: this.$t("modal.timeline.export_result.csv.use_timestamps"),
            // },
            // {
            //   field: "checkbox",
            //   name: "use_seconds",
            //   value: true,
            //   text: this.$t("modal.timeline.export_result.csv.use_seconds"),
            // },
            // {
            //   field: "checkbox",
            //   name: "include_category",
            //   value: true,
            //   text: this.$t("modal.timeline.export_result.csv.include_category"),
            // },
          ],
        },
        // {
        //   name: this.$t("modal.timeline.export_result.json.export_name"),
        //   icon: "mdi-file",
        //   export: "json",
        //   parameters: [],
        // },
      ],
    };
  },
  computed: {
    export_formats_sorted() {
      return this.export_formats.slice(0).sort((a, b) => a.name.localeCompare(b.name));
    },
    ...mapStores(useTimelineStore, usePluginRunResultStore),
  },
  methods: {
    async downloadExport() {
      const timelineStore = useTimelineStore();
      const pluginRunResultStore = usePluginRunResultStore();

      const timeline = timelineStore.get(this.timeline);
      const result = pluginRunResultStore.get(timeline.plugin_run_result_id);

      console.log(timeline);
      console.log(result);
      if (result.type === "SCALAR") {
        var csv = "time,data\n";
        for (let i = 0; i < result.data.time.length; i++) {
          // Runs 5 times, with values of step 0 through 4.
          csv += result.data.time[i];
          csv += ",";
          csv += result.data.y[i];
          csv += "\n";
        }
        // csvFileData.forEach(function(row) {
        //         csv += row.join(',');
        //         csv += "\n";
        // });

        // document.write(csv);

        var csvFile = new Blob([csv], { type: "text/csv" });
        var downloadLink = document.createElement("a");
        downloadLink.download = timeline.name + ".csv";
        downloadLink.href = window.URL.createObjectURL(csvFile);
        downloadLink.style.display = "none";

        document.body.appendChild(downloadLink);
        downloadLink.click();
        // var hiddenElement = document.createElement("a");
        // hiddenElement.href = "data:text/csv;charset=utf-8," + encodeURI(csv);
        // hiddenElement.target = "_blank";

        // //provide the name for the CSV file to be downloaded
        // hiddenElement.download = timeline.name + ".csv";
        // hiddenElement.click();
        this.dialog = false;
      }

      //   parameters = parameters.map((e) => {
      //     if ("file" in e) {
      //       return { name: e.name, file: e.file };
      //     } else {
      //       return { name: e.name, value: e.value };
      //     }
      //   });
      //   this.videoStore
      //     .export({ format: format, parameters: parameters })
      //     .then(() => {
      //       this.dialog = false;
      //     });
    },
  },
  watch: {
    dialog(value) {
      //   console.log(this.timeline);
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

<style scoped>
.color-map {
  width: 100%;
  height: 100%;
  min-width: 200px;
  min-height: 30px;
  border: 1px;
  border-color: gray;
  border-style: solid;
}

.color-map-list {
  width: 100%;
}
</style>



