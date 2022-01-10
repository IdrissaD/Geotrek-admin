$(window).on('entity:view:add entity:view:update', function (e, data) {
    $('#div_id_message_sentinel').prop('hidden', true);
    $('#div_id_message_supervisor').prop('hidden', true);
    $('#div_id_uses_timers').prop('hidden', true);
    $('#id_status').change(function () {
        display_message_fields_on_status_change();
    });
    $('#id_assigned_user').change(function () {
        display_message_fields_on_supervisor_change();
    });
    return;
});

function display_message_fields_on_status_change() {
    var status_ids_and_colors = JSON.parse($('#status_ids_and_colors').text());
    var selected = $('#id_status').val() || null;
    do_display = ((status_ids_and_colors[selected]['id'] == "resolved") || (status_ids_and_colors[selected]['id'] == "classified"))
    $('#div_id_message_sentinel').prop('hidden', !do_display);
    // Prevent assigning and classifying at the same time
    if (status_ids_and_colors[selected]['id'] == "classified") {
        $('#id_assigned_user').val("");
        $('#div_id_assigned_user').prop('hidden', true);
        $('#div_id_message_supervisor').prop('hidden', true);
        $('#div_id_uses_timers').prop('hidden', true);
    }
    if (status_ids_and_colors[selected]['id'] == "filed") {
        $('#id_assigned_user').val("");
        $('#div_id_assigned_user').prop('hidden', false);
    }
}

function display_message_fields_on_supervisor_change() {
    var selected = $('#id_assigned_user').val() || null;
    $('#div_id_message_sentinel').prop('hidden', (selected == null));
    $('#div_id_message_supervisor').prop('hidden', (selected == null));
    $('#div_id_uses_timers').prop('hidden', (selected == null));
}

function ChangeColors(e, data) {
    var map = data.map;
    // Remove normal reports layer
    map.eachLayer(function (layer) {
        if (layer.options['modelname'] === "report") {
            map.removeLayer(layer)
        }
    })
    function getUrl(properties, layer) {
        return window.SETTINGS.urls.detail.replace(new RegExp('modelname', 'g'), data.modelname)
            .replace('0', properties.pk);
    }
    // For each report status
    var status_ids_and_colors = JSON.parse($('#status_ids_and_colors').text());
    for (var status in status_ids_and_colors) {
        status_id = status_ids_and_colors[status]["id"]
        status_color = status_ids_and_colors[status]["color"]
        // Use this status' color...
        L.Util.extend(
            window.SETTINGS.map.styles["report-" + status_id] = { 'weight': 5, 'color': status_color, 'opacity': 0.9, fillOpacity: 0.9 },
        );
        // ... in creating layer with reports that have this status
        var layer = new L.ObjectsLayer(null, {
            modelname: "report-" + status_id,
            objectUrl: getUrl,
            style: { color: status_color },
        });
        layer.load("/api/report/report-" + status_id + ".geojson")
        map.addLayer(layer)
    }
}

$(window).on('entity:map:detail', ChangeColors);
$(window).on('entity:map:list', ChangeColors);