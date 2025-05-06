<template>
  <v-card>
    <v-toolbar color="primary" dark>Annotate Timeline Segment</v-toolbar>
    <v-card-text>
      <form>
        <v-text-field
          v-model="annotation.label"
          :counter="120"
          label="Label"
          required
        ></v-text-field>

        <v-btn class="mr-4" :disabled="disabled" @click="annotate_segment">
          Upload
        </v-btn>
        <v-btn @click="dialog = false">Close</v-btn>
      </form>
    </v-card-text>
  </v-card>
</template>


<script>
export default {
  data() {
    return {
      annotation: {},
    };
  },
  computed: {},
  methods: {
    annotate_segment() {
      console.log(this.annotation);
      this.dialog = false;
    },
  },
};
</script>