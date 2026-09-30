// The request form's groups (templates/absence/request.html): show only the
// ones the chosen type uses. Each type <option> carries its flags
// (absence/forms.py TypeSelect). Part of a day is not the type's business:
// it is on the page whenever the allowance is in hours, for any type, and
// left off it altogether for sessions, so this script never touches it.
// Without this script every group shows and the server blanks what does not
// apply; with it, a group that does not apply is hidden and disabled, so
// what it holds is kept for a change of mind but not sent.
(function () {
  "use strict";
  var select = document.getElementById("id_absence_type");
  if (!select || !select.form) return;
  var form = select.form;

  function set(name, show) {
    var group = form.querySelector('fieldset[data-group="' + name + '"]');
    if (!group) return;
    group.hidden = !show;
    group.disabled = !show;
  }

  function apply() {
    var option = select.options[select.selectedIndex];
    var flags = (option && option.dataset) || {};
    set("sick", flags.healthSensitive === "1");
    set("family", flags.family === "1");
  }

  select.addEventListener("change", apply);
  apply();
})();
