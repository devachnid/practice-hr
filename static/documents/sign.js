/* The sign page's passkey button (templates/documents/sign.html).
 *
 * Revealed only where the browser has PublicKeyCredential, as the Account
 * page's is; the password route needs no script. On a click: the form's own
 * check that the box is ticked, then a challenge from documents:passkey_options,
 * the browser's assertion, and the form submitted with the assertion's JSON in
 * the hidden `credential` field. The server checks the assertion and that the
 * passkey is the signed-in person's own (documents/views.py). The WebAuthn
 * plumbing is static/js/passkeys.js's, which exposes it as window.practicePasskeys
 * and loads first (both scripts are deferred, so they run in order).
 */
(function () {
  var button = document.getElementById("sign-passkey");
  var pk = window.practicePasskeys;
  if (!button || !pk || !window.PublicKeyCredential) { return; }
  var form = document.getElementById("sign-form");
  var field = document.getElementById("sign-credential");
  var errorEl = document.getElementById("sign-passkey-error");
  button.style.display = "";
  button.addEventListener("click", function () {
    if (button.disabled || !form.reportValidity()) { return; }
    button.disabled = true;
    pk.show(errorEl, "");
    Promise.resolve().then(function () {     // so a throw here lands in the catch, not on the console
      return pk.post(button.dataset.optionsUrl, pk.csrfToken(form));
    }).then(function (opts) {
      return navigator.credentials.get({ publicKey: pk.requestOptions(opts) });
    }).then(function (cred) {
      field.value = JSON.stringify(pk.credentialToJSON(cred));
      var password = form.querySelector("[name=password]");
      if (password) { password.value = ""; }
      pk.remember();
      form.submit();
    }).catch(function (e) {
      field.value = "";
      pk.show(errorEl, pk.explain(e));
      button.disabled = false;
    });
  });
})();
