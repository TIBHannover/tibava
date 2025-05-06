<template>
  <v-dialog v-model="dialog" max-width="90%">
    <v-card>
      <v-card-title class="mb-2">
        {{ $t("modal.error.title") }}

        <v-btn icon @click="clearError()" absolute right>
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text>
        {{ errorMessage }}
      </v-card-text>
      <v-card-actions class="pt-0">
        <v-btn @click="clearError()">{{ $t("modal.error.close") }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script>
import { mapStores } from "pinia";
import { useErrorStore } from "@/store/error";

export default {
  data() {
    return {
      dialog: false,
    };
  },
  computed: {
    errorDate() {
      return this.errorStore.error_date;
    },
    errorComponent() {
      return this.errorStore.error_component;
    },
    errorMessage() {
      return this.errorStore.errorMessage;
    },
    error() {
      return this.errorStore.error;
    },
    ...mapStores(useErrorStore),
  },
  methods: {
    clearError() {
      this.dialog = false;
    },
  },
  watch: {
    error(value) {
      if (value) {
        this.dialog = true;
      }
    }
  }
};
</script>
