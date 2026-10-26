import Foundation
import Darwin

public enum PortError: Error { case socket, bind, name }

/// A free TCP port on the loopback address.
public enum Port {
    public static let host = "127.0.0.1"

    /// binds port 0 on 127.0.0.1, reads the port that the system gave, then closes the socket
    public static func free() throws -> Int {
        let fd = socket(AF_INET, SOCK_STREAM, 0)
        guard fd >= 0 else { throw PortError.socket }
        defer { close(fd) }
        var addr = sockaddr_in()
        addr.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
        addr.sin_family = sa_family_t(AF_INET)
        addr.sin_port = 0
        addr.sin_addr.s_addr = inet_addr(host)
        let size = socklen_t(MemoryLayout<sockaddr_in>.size)
        let ok = withUnsafeMutablePointer(to: &addr) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { bind(fd, $0, size) }
        }
        guard ok == 0 else { throw PortError.bind }
        var len = size
        let got = withUnsafeMutablePointer(to: &addr) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { getsockname(fd, $0, &len) }
        }
        guard got == 0 else { throw PortError.name }
        return Int(UInt16(bigEndian: addr.sin_port))
    }

    public static func base(_ port: Int) -> URL { URL(string: "http://\(host):\(port)/")! }
}
