<template>
  <v-dialog v-model="show" max-width="1000">
    <template v-slot:activator="{ on }">
      <v-btn v-on="on" text block large>
        <v-icon left>{{ "mdi-import" }}</v-icon>
        {{ $t("modal.timeline.import.title") }}
      </v-btn>
    </template>
    <v-card>
      <v-card-title class="mb-2">
        {{ $t("modal.timeline.import.title") }}

        <v-btn icon @click.native="show = false" absolute top right>
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text>
        <!-- <v-row lign="center" justify="center">
          <v-btn @click="importEAF" height="100px" class="mx-2">
            <div class="mx-auto text-center">
              <p>
                <v-icon x-large> mdi-file </v-icon>
              </p>
              {{ $t("modal.timeline.import.eaf") }}
            </div>
          </v-btn> -->
          <!-- <v-btn @click="downloadJson" height="100px" class="mx-2">
            <div class="mx-auto text-center">
              <p>
                <v-icon x-large> mdi-file </v-icon>
              </p>
              {{ $t("modal.export.json") }}
            </div>
          </v-btn>
        </v-row>-->
          <v-file-input
            v-model="importfile"
            label="Select an ELAN file to import [eaf]"
            filled
            prepend-icon="mdi-file"
          ></v-file-input>
      </v-card-text>
      <v-card-actions class="pt-0">
        <v-btn class="mr-4" @click="submit" :disabled="isSubmitting">
          {{ $t("modal.timeline.import.update") }}
        </v-btn>
        <v-btn @click="show = false">{{
          $t("modal.timeline.import.close")
        }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script>
import { mapStores } from "pinia";
import { useTimelineStore } from "@/store/timeline";

export default {
  data() {
    return {
      show: false,
      isSubmitting: false,
      importfile: null,
      name: null,
      items: [],
    };
  },
  computed: {
    ...mapStores(useTimelineStore),
  },
  methods: {
    async submit() {
      if (this.isSubmitting) {
        return;
      }
      this.isSubmitting = true;

      await this.timelineStore.importEAF({
        importfile: this.importfile,
      });

      this.isSubmitting = false;
      this.show = false;
    },
  },
  watch: {
    show(value) {
      if (value) {
        this.name = null;
        this.$emit("close");
      }
    },
  },
};
</script>
