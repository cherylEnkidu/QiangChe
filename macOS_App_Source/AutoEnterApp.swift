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
        if CommandLine.arguments.contains("--test-return") {
            guard CGPreflightPostEventAccess() else {
                print("测试停止：此应用缺少发送按键权限")
                exit(2)
            }
            var receivedDown = false
            NSEvent.addLocalMonitorForEvents(matching: [.keyDown, .keyUp]) { event in
                if event.keyCode == 36 {
                    if event.type == .keyDown { receivedDown = true }
                    if receivedDown && event.type == .keyUp {
                        print("测试窗口收到 Return 按下和释放")
                        exit(0)
                    }
                    return nil
                }
                return event
            }
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                _ = postReturn(to: ProcessInfo.processInfo.processIdentifier)
            }
            DispatchQueue.main.asyncAfter(deadline: .now() + 3) { exit(3) }
            return
        }
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

    @State private var useWeChatRTT = false

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
                    .disabled(useWeChatRTT || isRunning)
            }

            Toggle("微信 RTT 自动补偿", isOn: $useWeChatRTT)
                .disabled(isRunning)
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
        .frame(width: 480, height: 350)
    }

    func startTimer() {
        guard CGPreflightPostEventAccess() else {
            statusMsg = "没有发送按键权限。请在系统设置 → 隐私与安全性 → 辅助功能中启用此应用，再重新打开。"
            return
        }
        let manualLead = Int(leadMsStr)
        guard useWeChatRTT || manualLead != nil else {
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
        guard targetDate > Date() else {
            statusMsg = "目标时间已过，请重新设置。"
            return
        }
        let automatic = useWeChatRTT
        isRunning = true
        statusMsg = automatic ? "请点击目标输入框。将在目标前约 10 秒采样微信 RTT…" : "正在启动定时…"

        DispatchQueue.global(qos: .userInteractive).async {
            let leadMs: Int
            if automatic {
                Thread.sleep(until: targetDate.addingTimeInterval(-10))
                let count = max(1, min(10, Int(targetDate.timeIntervalSinceNow + 0.25)))
                DispatchQueue.main.async { self.statusMsg = "正在采样微信 RTT（最多 \(count) 次）…" }
                guard let measured = Self.weChatLead(count: count) else {
                    DispatchQueue.main.async {
                        self.isRunning = false
                        self.statusMsg = "无法读取微信 RTT，请确认微信已联网后重试。"
                    }
                    return
                }
                leadMs = measured
            } else {
                leadMs = manualLead ?? 80
            }
            let fireTs = targetTimestamp - Double(leadMs) / 1000
            guard fireTs > Date().timeIntervalSince1970 else {
                DispatchQueue.main.async {
                    self.isRunning = false
                    self.statusMsg = "补偿后的触发时间已过，请重新设置。"
                }
                return
            }
            var warningPrinted = false
            while true {
                let now = Date().timeIntervalSince1970
                let remaining = fireTs - now
                if remaining <= 0 {
                    break
                }
                
                if remaining > 2.0 {
                    DispatchQueue.main.async {
                        self.statusMsg = String(format: "⏳ 等待中... 剩余 %.1f 秒（提前 %d ms）", remaining, leadMs)
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

            let front = NSWorkspace.shared.frontmostApplication
            let posted = front.map { postReturn(to: $0.processIdentifier) } ?? false
            let fired = Date()
            DispatchQueue.main.async {
                self.isRunning = false
                let formatter = DateFormatter()
                formatter.dateFormat = "HH:mm:ss.SSS"
                self.statusMsg = posted
                    ? "已于 \(formatter.string(from: fired)) 向「\(front?.localizedName ?? "前台应用")」投递回车（提前 \(leadMs) ms）。"
                    : "未投递回车，请检查辅助功能权限和前台窗口。"
            }
        }
    }

    private static func weChatLead(count: Int) -> Int? {
        guard let script = Bundle.main.url(forResource: "wechat-rtt", withExtension: "sh") else { return nil }
        let process = Process()
        let output = Pipe()
        process.executableURL = URL(fileURLWithPath: "/bin/bash")
        process.arguments = [script.path, String(count)]
        process.standardOutput = output
        do { try process.run() } catch { return nil }
        process.waitUntilExit()
        guard process.terminationStatus == 0 else { return nil }
        let data = output.fileHandleForReading.readDataToEndOfFile()
        return String(data: data, encoding: .utf8).flatMap { Int($0.trimmingCharacters(in: .whitespacesAndNewlines)) }
    }

}

private func postReturn(to pid: pid_t) -> Bool {
    guard CGPreflightPostEventAccess(),
          let down = CGEvent(keyboardEventSource: nil, virtualKey: 36, keyDown: true),
          let up = CGEvent(keyboardEventSource: nil, virtualKey: 36, keyDown: false) else { return false }
    down.postToPid(pid)
    up.postToPid(pid)
    return true
}
