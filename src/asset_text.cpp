/*
 * ps5-native-app-boilerplate - Read text assets on the console and test hosts.
 * Copyright (C) 2026 BlackBearReloaded
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

#include "demo_renderer.hpp"

#include <algorithm>
#include <fcntl.h>
#include <unistd.h>

namespace ps5::demo
{
void read_asset_text(const char *path, std::span<char> destination,
                     std::string_view fallback) noexcept
{
    if (destination.empty())
        return;
    const auto fallback_size = std::min(fallback.size(), destination.size() - 1);
    for (std::size_t index = 0; index < fallback_size; ++index)
        destination[index] = fallback[index];
    destination[fallback_size] = '\0';

    const int descriptor = open(path, O_RDONLY);
    if (descriptor < 0)
        return;
    const auto count = read(descriptor, destination.data(), destination.size() - 1);
    (void)close(descriptor);
    if (count <= 0)
        return;

    std::size_t length = static_cast<std::size_t>(count);
    while (length > 0 && (destination[length - 1] == '\r' || destination[length - 1] == '\n'))
        --length;
    destination[length] = '\0';
}
} // namespace ps5::demo
