<template>
  <v-dialog v-model="show" max-width="1000">
    <template v-slot:activator="{ on }">
      <v-btn v-on="on" text block large>
        <v-icon left>{{ "mdi-pencil" }}</v-icon>
        {{ $t("modal.timeline.rename.link") }}
      </v-btn>
    </template>
    <v-card>
      <v-card-title class="mb-2">
        {{ $t("modal.timeline.rename.title") }}

        <v-btn icon @click.native="show = false" absolute top right>
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text>
        <v-text-field
          :label="$t('modal.timeline.rename.name')"
          prepend-icon="mdi-pencil"
          v-model="name"
        ></v-text-field>
      </v-card-text>
      <v-card-actions class="pt-0">
        <v-btn class="mr-4" @click="submit" :disabled="isSubmitting || !name">
          {{ $t("modal.timeline.rename.update") }}
        </v-btn>
        <v-btn @click="show = false">{{
          $t("modal.timeline.rename.close")
        }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script>
import { mapStores } from "pinia";
import { useTimelineStore } from "@/store/timeline";

export default {
  props: ["timeline"],
  data() {
    return {
      show: false,
      isSubmitting: false,
      nameProxy: null,
      items: [],
    };
  },
  computed: {
    name: {
      get() {
        const name = this.timelineStore.get(this.timeline).name;
        return this.nameProxy === null ? name : this.nameProxy;
      },
      set(val) {
        this.nameProxy = val;
      },
    },
    ...mapStores(useTimelineStore),
  },
  methods: {
    async submit() {
      if (this.isSubmitting) {
        return;
      }
      this.isSubmitting = true;

      await this.timelineStore.rename({
        timelineId: this.timeline,
        name: this.name,
      });

      this.isSubmitting = false;
      this.show = false;
    },
  },
  watch: {
    show(value) {
      if (value) {
        this.nameProxy = null;
        this.$emit("close");
      }
    },
  },
};
</script>
