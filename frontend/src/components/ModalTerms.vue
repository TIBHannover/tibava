<template>
  <v-dialog v-model="dialog" width="90%" max-width="1000px">
    <template v-slot:activator="{ on, attrs }">
      <slot name="activator" :on="on" :attrs="attrs">
        <v-btn tile text v-bind="attrs" v-on="on">
          <v-icon>{{ "mdi-plus" }}</v-icon>
          {{ $t("modal.terms.link") }}
        </v-btn>
      </slot>
    </template>

    <v-card height="80vh" class="d-flex flex-column">
      <v-card-title>
        {{ $t("modal.terms.title") }}
      </v-card-title>
      <v-card-text style="overflow-y: scroll">
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
      </v-card-text>

      <v-spacer></v-spacer>
      <v-card-actions class="pt-0">
        <v-btn class="mr-4" :disabled="!checkbox" @click="accept_terms()">
          {{ $t("modal.terms.accept") }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script>
import { mapStores } from "pinia";
import { useVideoStore } from "@/store/video";
import { usePlayerStore } from "@/store/player";

export default {
  props: ["value", "videoId"],
  data() {
    return {
      dialog: false,
      checkbox: false,
      isSubmitting: false,
    };
  },
  computed: {
    ...mapStores(useVideoStore),
    ...mapStores(usePlayerStore),
  },
  methods: {
    async accept_terms() {
      if (this.isSubmitting) {
        return;
      }
      this.isSubmitting = true;

      let result = await this.videoStore.accept_terms({
        videoId: this.videoId,
      });

      if (result) {
        this.playerStore.video.accept_terms = true;
        this.isSubmitting = false;
        this.dialog = false;
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
