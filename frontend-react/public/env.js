(function (window) {
  window.env = window.env || {};

  // Development defaults. In production this file is regenerated from
  // env.template.js by start.sh (envsubst) inside the Docker image.
  window.env.API_SERVER_URL = '/api';
  window.env.ENABLE_FEDML_BLOCKCHAIN = '0';
})(this);
