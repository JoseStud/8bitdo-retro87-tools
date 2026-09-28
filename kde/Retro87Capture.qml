// Loaded inside Waywallen's wallpaper. Captures only its rendered surface.
import QtQuick
import org.kde.plasma.workspace.dbus as DBus

Item {
    id: bridge
    required property Item sourceItem
    required property string screenName
    property bool busy: false

    function call(member, args, done) {
        DBus.SessionBus.asyncCall({
            service: "io.github.JoseStud.Retro87", path: "/io/github/JoseStud/Retro87",
            iface: "io.github.JoseStud.Retro87", member: member, arguments: args
        }, function(reply) { done(reply.value.value) },
           function(error) { bridge.busy = false })
    }

    Timer {
        interval: 100  // The service paces frames: 10/s over USB, 2/s over 2.4 GHz
        repeat: true
        running: true
        onTriggered: {
            if (bridge.busy || !bridge.sourceItem || bridge.sourceItem.width <= 0 || bridge.sourceItem.height <= 0)
                return
            bridge.busy = true
            bridge.call("WallpaperFrameTarget", [bridge.screenName], function(path) {
                if (!path) {
                    bridge.busy = false
                    return
                }
                const source = bridge.sourceItem
                if (!source) {
                    bridge.busy = false
                    return
                }
                const scale = 192 / Math.max(source.width, source.height)
                const size = Qt.size(Math.max(1, Math.round(source.width * scale)),
                                     Math.max(1, Math.round(source.height * scale)))
                const started = source.grabToImage(function(result) {
                    if (!result.saveToFile(path)) {
                        bridge.busy = false
                        return
                    }
                    bridge.call("WallpaperFrame", [path], function(state) { bridge.busy = false })
                }, size)
                if (!started)
                    bridge.busy = false
            })
        }
    }
}
