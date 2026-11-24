/*
 * ps5-native-app-boilerplate - Host tests for reusable application behavior.
 * Copyright (C) 2026 BlackBearReloaded
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * Validates bounded asset loading without requiring PS5 hardware.
 */

#include "frame_submission.hpp"
#include "demo_renderer.hpp"

#include <gtest/gtest.h>
#include <utility>
#include <vector>

#include <array>
#include <cstdio>
#include <fstream>
#include <span>

namespace
{
class AssetTextTest : public testing::Test
{
  protected:
    static constexpr const char *missing_path = "build/tests/missing-banner.txt";
    static constexpr const char *asset_path = "build/tests/banner.txt";

    void SetUp() override
    {
        (void)std::remove(missing_path);
        std::ofstream asset{asset_path, std::ios::binary};
        ASSERT_TRUE(asset.is_open());
        asset << "FROM APP0\r\n";
        ASSERT_TRUE(asset.good());
    }

    void TearDown() override
    {
        (void)std::remove(asset_path);
        (void)std::remove(missing_path);
    }
};

TEST_F(AssetTextTest, MissingAssetUsesFallback)
{
    std::array<char, 32> text{};
    ps5::demo::read_asset_text(missing_path, std::span{text}, "FALLBACK");
    EXPECT_STREQ(text.data(), "FALLBACK");
}

TEST_F(AssetTextTest, AssetTextTrimsLineEndings)
{
    std::array<char, 32> text{};
    ps5::demo::read_asset_text(asset_path, std::span{text}, "FALLBACK");
    EXPECT_STREQ(text.data(), "FROM APP0");
}

TEST_F(AssetTextTest, AssetTextRemainsNullTerminatedWhenTruncated)
{
    std::array<char, 5> bounded{};
    ps5::demo::read_asset_text(asset_path, std::span{bounded}, "FALLBACK");
    EXPECT_STREQ(bounded.data(), "FROM");
}
} // namespace

TEST(FrameSubmissionTest, RetriesPendingBufferWithoutRedrawingOrAdvancing)
{
    ps5::demo::detail::FrameSubmission frames;
    std::vector<int> drawn;
    std::vector<std::pair<int, std::uint64_t>> submitted;
    int waits = 0;
    const auto draw = [&](int buffer) { drawn.push_back(buffer); };
    const auto submit = [&](int buffer, std::uint64_t frame)
    {
        submitted.emplace_back(buffer, frame);
        return submitted.size() != 2;
    };
    const auto wait = [&] { return ++waits > 0; };

    ASSERT_TRUE(frames.present_next(draw, submit, wait));
    ASSERT_TRUE(frames.present_next(draw, submit, wait));
    ASSERT_TRUE(frames.present_next(draw, submit, wait));
    EXPECT_EQ(drawn, (std::vector<int>{1, 0, 1}));
    EXPECT_EQ(submitted,
              (std::vector<std::pair<int, std::uint64_t>>{{1, 2}, {0, 3}, {0, 3}, {1, 4}}));
    EXPECT_EQ(waits, 4);
}

TEST(FrameSubmissionTest, StopsAfterRepeatedRefusals)
{
    ps5::demo::detail::FrameSubmission frames;
    int draws = 0, submits = 0;
    EXPECT_FALSE(frames.present_next(
        [&](int buffer)
        {
            EXPECT_EQ(buffer, 1);
            ++draws;
        },
        [&](int buffer, std::uint64_t frame)
        {
            EXPECT_EQ(buffer, 1);
            EXPECT_EQ(frame, 2u);
            ++submits;
            return false;
        },
        [] { return true; }));
    EXPECT_EQ(draws, 1);
    EXPECT_EQ(submits, 4);
}
