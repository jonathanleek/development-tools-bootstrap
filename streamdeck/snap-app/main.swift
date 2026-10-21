// Whiteboard Snap: takes one still from a webcam, as an app, so macOS can ask
// once for camera access. A process the Stream Deck plugin starts directly is
// refused without a prompt; one started through LaunchServices as an app is
// asked.
//
//   open -W -n "Whiteboard Snap.app" --args <camera name> <out.png>
//
// The still is a frame from the video stream (AVCaptureVideoDataOutput), not
// a photo capture: the Insta360 Link fails AVCapturePhotoOutput, which is
// what imagesnap uses. Frames from the first WARMUP seconds are skipped so
// exposure and focus settle. On failure the reason goes to <out.png>.err
// (open -W can't pass an exit status back).
import AVFoundation
import CoreImage
import Foundation
import ImageIO
import UniformTypeIdentifiers

let WARMUP: TimeInterval = 1.0
let TIMEOUT: TimeInterval = 15.0

let args = Array(CommandLine.arguments.dropFirst())
guard args.count == 2 else { exit(64) }
let (cameraName, out) = (args[0], args[1])

func fail(_ message: String) -> Never {
    try? message.write(toFile: out + ".err", atomically: true, encoding: .utf8)
    exit(1)
}

// Ask (or check) for camera access as this app; prompts the first time.
let asked = DispatchSemaphore(value: 0)
var granted = false
AVCaptureDevice.requestAccess(for: .video) { ok in granted = ok; asked.signal() }
asked.wait()
if !granted {
    fail("camera access denied for Whiteboard Snap (System Settings > Privacy & Security > Camera)")
}

// External cameras can take a moment to be listed in a freshly started app.
func findCamera() -> (AVCaptureDevice?, [String]) {
    let found = AVCaptureDevice.DiscoverySession(
        deviceTypes: [.external, .builtInWideAngleCamera], mediaType: .video, position: .unspecified
    ).devices
    return (found.first(where: { $0.localizedName == cameraName }), found.map(\.localizedName))
}
var (match, seen) = findCamera()
let lookUntil = Date().addingTimeInterval(3)
while match == nil && Date() < lookUntil {
    RunLoop.main.run(until: Date().addingTimeInterval(0.1))
    (match, seen) = findCamera()
}
guard let camera = match else {
    fail("no camera named \(cameraName); found: \(seen.joined(separator: ", "))")
}

final class Grabber: NSObject, AVCaptureVideoDataOutputSampleBufferDelegate {
    let start = Date()
    let done = DispatchSemaphore(value: 0)
    var image: CGImage?

    func captureOutput(_ output: AVCaptureOutput, didOutput sample: CMSampleBuffer, from connection: AVCaptureConnection) {
        guard image == nil, Date().timeIntervalSince(start) >= WARMUP,
              let pixels = CMSampleBufferGetImageBuffer(sample) else { return }
        let ci = CIImage(cvPixelBuffer: pixels)
        image = CIContext().createCGImage(ci, from: ci.extent)
        done.signal()
    }
}

let session = AVCaptureSession()
session.sessionPreset = .high
do {
    let input = try AVCaptureDeviceInput(device: camera)
    guard session.canAddInput(input) else { fail("cannot use \(cameraName) as input") }
    session.addInput(input)
} catch {
    fail("cannot open \(cameraName): \(error.localizedDescription)")
}
let output = AVCaptureVideoDataOutput()
output.videoSettings = [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA]
let grabber = Grabber()
output.setSampleBufferDelegate(grabber, queue: DispatchQueue(label: "frames"))
guard session.canAddOutput(output) else { fail("cannot read frames from \(cameraName)") }
session.addOutput(output)
session.startRunning()

// Keep the main run loop turning while waiting: the capture session needs it
// to start the device (blocking on the semaphore here yields no frames).
let deadline = Date().addingTimeInterval(TIMEOUT)
while grabber.done.wait(timeout: .now()) == .timedOut {
    if Date() > deadline {
        session.stopRunning()
        fail("no frame from \(cameraName) within \(Int(TIMEOUT)) s")
    }
    RunLoop.main.run(until: Date().addingTimeInterval(0.05))
}
session.stopRunning()

guard let still = grabber.image,
      let dest = CGImageDestinationCreateWithURL(URL(fileURLWithPath: out) as CFURL, UTType.png.identifier as CFString, 1, nil)
else { fail("could not encode the frame") }
CGImageDestinationAddImage(dest, still, nil)
if !CGImageDestinationFinalize(dest) { fail("could not write \(out)") }
exit(0)
