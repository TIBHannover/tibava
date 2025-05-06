import Vue from 'vue';
import Vuetify from 'vuetify';
import 'vuetify/dist/vuetify.min.css';
import '@mdi/font/css/materialdesignicons.css';

Vue.use(Vuetify);
export default new Vuetify({
  theme: {
    themes: {
      light: {
        primary: '#1D3557',
        secondary: '#457B9D',
        accent: '#E63946',
      },
    },
  },
});
