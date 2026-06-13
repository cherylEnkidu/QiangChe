import SwiftUI
import CoreGraphics
import AppKit

@main
struct AutoEnterApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}

class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        // Request Accessibility Permissions if we don't have them
        let options: NSDictionary = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String : true]
        let accessEnabled = AXIsProcessTrustedWithOptions(options)
        if !accessEnabled {
            print("Accessibility Permissions not enabled. Prompting user...")
        }
    }
}

struct ContentView: View {
    @State private var targetTimeStr: String = "18:00:00.000"
    @State private var leadMsStr: String = "80"
    @State private var statusMsg: String = "空闲"
    @State private var isRunning = false

    var body: some View {
        VStack(spacing: 20) {
            Text("定时回车助手")
                .font(.largeTitle)
                .padding(.top, 10)

            HStack {
                Text("目标时间:")
                TextField("HH:mm:ss.SSS", text: $targetTimeStr)
                    .textFieldStyle(RoundedBorderTextFieldStyle())
                    .frame(width: 150)
                
                Button("下一分钟 (测试)") {
                    var components = Calendar.current.dateComponents([.year, .month, .day, .hour, .minute], from: Date())
                    components.minute = (components.minute ?? 0) + 1
                    components.second = 0
                    if let nextMin = Calendar.current.date(from: components) {
                        let formatter = DateFormatter()
                        formatter.dateFormat = "HH:mm:ss.000"
                        targetTimeStr = formatter.string(from: nextMin)
                    }
                }
                .disabled(isRunning)
            }

            HStack {
                Text("提前量 (毫秒):")
                TextField("80", text: $leadMsStr)
                    .textFieldStyle(RoundedBorderTextFieldStyle())
                    .frame(width: 80)
            }

            Button(action: {
                startTimer()
            }) {
                Text(isRunning ? "运行中..." : "开始定时")
                    .padding(.horizontal, 20)
                    .padding(.vertical, 5)
            }
            .disabled(isRunning)

            Text(statusMsg)
                .foregroundColor(isRunning ? .orange : .primary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 20)
        }
        .padding(30)
        .frame(width: 480, height: 300)
    }

    func startTimer() {
        guard let leadMs = Int(leadMsStr) else {
            statusMsg = "无效的提前量"
            return
        }

        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        let todayStr = formatter.string(from: Date())
        
        formatter.dateFormat = "yyyy-MM-dd HH:mm:ss.SSS"
        guard let targetDate = formatter.date(from: "\(todayStr) \(targetTimeStr)") else {
            statusMsg = "目标时间格式无效 (需要 HH:mm:ss.SSS)"
            return
        }

        let targetTimestamp = targetDate.timeIntervalSince1970
        let fireTs = targetTimestamp - (Double(leadMs) / 1000.0)

        if fireTs < Date().timeIntervalSince1970 {
            statusMsg = "警告: 目标时间已过去！请等待至明天。"
            return
        }

        isRunning = true
        statusMsg = "已预约 \(targetTimeStr)。\n请立即切换到目标窗口！"

        // Run in background thread
        DispatchQueue.global(qos: .userInteractive).async {
            var warningPrinted = false
            while true {
                let now = Date().timeIntervalSince1970
                let remaining = fireTs - now
                if remaining <= 0 {
                    break
                }
                
                if remaining > 2.0 {
                    DispatchQueue.main.async {
                        self.statusMsg = String(format: "⏳ 等待中... 剩余 %.1f 秒", remaining)
                    }
                    Thread.sleep(forTimeInterval: 0.1)
                } else if remaining > 0.2 {
                    if !warningPrinted {
                        DispatchQueue.main.async {
                            self.statusMsg = "⚠️ 准备触发！\n(请保持窗口聚焦，不要移动鼠标)"
                        }
                        warningPrinted = true
                    }
                    Thread.sleep(forTimeInterval: remaining - 0.2)
                } else {
                    // Busy wait for the last 200ms
                }
            }

            // Busy wait for the last 200ms
            while true {
                if Date().timeIntervalSince1970 >= fireTs {
                    break
                }
            }

            // Fire the enter key
            self.pressEnter()

            DispatchQueue.main.async {
                self.isRunning = false
                let finalFormatter = DateFormatter()
                finalFormatter.dateFormat = "HH:mm:ss.SSS"
                self.statusMsg = "✅ 已精确发送于 \(finalFormatter.string(from: Date()))！"
            }
        }
    }

    func pressEnter() {
        let enterCode: CGKeyCode = 36 // 36 is the virtual key code for Return/Enter on macOS
        guard let keyDown = CGEvent(keyboardEventSource: nil, virtualKey: enterCode, keyDown: true),
              let keyUp = CGEvent(keyboardEventSource: nil, virtualKey: enterCode, keyDown: false) else {
            return
        }
        keyDown.post(tap: .cghidEventTap)
        keyUp.post(tap: .cghidEventTap)
    }
}
