#include "httplib.h"
#include <iostream>
#include <string>

int main(int argc, char **argv) {
    if (argc != 2) return 2;
    std::string url = argv[1];
    for (int hop = 0; hop < 10; ++hop) {
        if (url.rfind("https://", 0) != 0) return 2;
        const auto split = url.find('/', 8);
        const auto origin = url.substr(0, split);
        const auto path = split == std::string::npos ? "/" : url.substr(split);
        httplib::Client client(origin);
        client.set_connection_timeout(60, 0);
        client.set_read_timeout(60, 0);
        client.set_write_timeout(60, 0);
        client.enable_server_certificate_verification(true);
        client.set_follow_location(false);
        std::cout << "HEAD " << url << std::endl;
        const auto result = client.Head(path, {{"User-Agent", "audio.cpp native model manager/1.0"}});
        if (!result) {
            std::cout << "error=" << httplib::to_string(result.error())
                      << " ssl_error=" << result.ssl_error()
                      << " ssl_backend_error=" << result.ssl_backend_error()
                      << " hex=0x" << std::hex << result.ssl_backend_error() << std::dec << std::endl;
            return 1;
        }
        std::cout << "status=" << result->status
                  << " length=" << result->get_header_value("Content-Length") << std::endl;
        if (result->status >= 300 && result->status < 400 && result->has_header("Location")) {
            url = result->get_header_value("Location");
            if (!url.empty() && url.front() == '/') url = origin + url;
            continue;
        }
        return result->status == 200 ? 0 : 1;
    }
    return 2;
}
