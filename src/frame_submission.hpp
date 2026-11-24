/*
 * ps5-native-app-boilerplate - Display buffer submission and retry.
 * Copyright (C) 2026 BlackBearReloaded
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
#pragma once

#include <cstdint>

namespace ps5::demo::detail
{
class FrameSubmission
{
  public:
    // Buffer zero was submitted and presented by initialization.
    template <typename Draw, typename Submit, typename Wait>
    bool present_next(Draw draw, Submit submit, Wait wait) noexcept
    {
        const int pending = 1 - displayed_;
        draw(pending);
        constexpr int attempts = 4;
        for (int attempt = 0; attempt < attempts; ++attempt)
        {
            const bool submitted = submit(pending, frame_);
            if (!wait())
                return false;
            if (submitted)
            {
                displayed_ = pending;
                ++frame_;
                return true;
            }
        }
        return false;
    }

  private:
    int displayed_ = 0;
    std::uint64_t frame_ = 2;
};
} // namespace ps5::demo::detail
