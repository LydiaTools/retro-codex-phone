// Independent media-event adapter for Retro Codex Phone. MIT, LydiaHub 2026.
import AppKit
import CoreGraphics
import Foundation

func emit(_ value: [String: String]) {
    if let data = try? JSONSerialization.data(withJSONObject: value),
       let line = String(data: data, encoding: .utf8) {
        print(line)
        fflush(stdout)
    }
}

if !CGPreflightListenEventAccess() {
    emit(["status": "Input Monitoring permission is needed for phone buttons. Enable it for your terminal or launcher in System Settings, then retry. On-screen controls still work."])
    exit(3)
}

var tap: CFMachPort?
let callback: CGEventTapCallBack = { _, type, event, _ in
    if type == .tapDisabledByTimeout || type == .tapDisabledByUserInput {
        if let current = tap { CGEvent.tapEnable(tap: current, enable: true) }
        return Unmanaged.passUnretained(event)
    }
    guard type.rawValue == 14, let native = NSEvent(cgEvent: event), native.subtype.rawValue == 8 else {
        return Unmanaged.passUnretained(event)
    }
    let value = native.data1
    let code = (value >> 16) & 0xffff
    let flags = value & 0xffff
    let name = [16: "play", 0: "up", 1: "down"][code]
    guard let name else { return Unmanaged.passUnretained(event) }
    if (flags & 0xff00) == 0x0a00 && (flags & 1) == 0 { emit(["key": name]) }
    // Only these three media keys are consumed, and only while the user enables the listener.
    return nil
}

tap = CGEvent.tapCreate(tap: .cgSessionEventTap, place: .headInsertEventTap,
                       options: .defaultTap, eventsOfInterest: CGEventMask(1 << 14),
                       callback: callback, userInfo: nil)
guard let active = tap else {
    emit(["status": "macOS could not start the media-key reader. Check Input Monitoring and Accessibility for your launcher, then retry."])
    exit(4)
}
let source = CFMachPortCreateRunLoopSource(kCFAllocatorDefault, active, 0)
CFRunLoopAddSource(CFRunLoopGetMain(), source, .commonModes)
CGEvent.tapEnable(tap: active, enable: true)
emit(["status": "Listening for phone buttons. Test each button once."])
CFRunLoopRun()
