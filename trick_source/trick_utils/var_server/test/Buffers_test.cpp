#include "trick/vs/LineReader.hh"
#include "trick/vs/WriteQueue.hh"

#include <string>

#include <gtest/gtest.h>

using namespace Trick::vs;

// ---------------------------------------------------------------------------
// LineReader
// ---------------------------------------------------------------------------

TEST(LineReader, ABatchIsEveryCompleteLine)
{
    LineReader r;
    std::string b;
    r.append("trick.var_add(\"a\")\ntrick.var_se");
    ASSERT_TRUE(r.next_batch(b));
    EXPECT_EQ(b, "trick.var_add(\"a\")\n");
    EXPECT_FALSE(r.next_batch(b));
    EXPECT_EQ(r.pending(), 12u);
    r.append("nd()\ntrick.var_clear()\n");
    ASSERT_TRUE(r.next_batch(b));
    EXPECT_EQ(b, "trick.var_send()\ntrick.var_clear()\n");
    EXPECT_EQ(r.pending(), 0u);
}

TEST(LineReader, CarriageReturnsAreRemoved)
{
    LineReader r;
    std::string b;
    r.append("a\r\nb\rc\r\n");
    ASSERT_TRUE(r.next_batch(b));
    EXPECT_EQ(b, "a\nbc\n");
}

TEST(LineReader, ByteAtATime)
{
    LineReader r;
    std::string b;
    const std::string text = "x = 1\ny = 2\n";
    for (std::size_t i = 0; i + 1 < text.size(); ++i)
    {
        r.append(text.substr(i, 1));
        if (r.next_batch(b))
        {
            EXPECT_EQ(b, "x = 1\n");
        }
    }
    r.append("\n");
    ASSERT_TRUE(r.next_batch(b));
    EXPECT_EQ(b, "y = 2\n");
}

TEST(LineReader, ALineOfExactlyTheLimitIsKept)
{
    LineReader r(10);
    std::string b;
    r.append(std::string(10, 'a') + "\n");
    ASSERT_TRUE(r.next_batch(b));
    EXPECT_EQ(b, std::string(10, 'a') + "\n");
    EXPECT_EQ(r.take_discarded(), 0u);
}

TEST(LineReader, AnOverlongLineIsDiscardedUpToItsNewline)
{
    // The old reader stalled for good on a line of 200000 bytes or more.
    LineReader r(10);
    std::string b;
    r.append("ok\n" + std::string(11, 'x'));
    EXPECT_TRUE(r.discarding());
    ASSERT_TRUE(r.next_batch(b));
    EXPECT_EQ(b, "ok\n");
    r.append(std::string(500, 'x'));
    EXPECT_FALSE(r.next_batch(b));
    EXPECT_EQ(r.pending(), 0u); // nothing of the long line is held
    r.append("xx\nnext\n");
    EXPECT_FALSE(r.discarding());
    ASSERT_TRUE(r.next_batch(b));
    EXPECT_EQ(b, "next\n");
    EXPECT_EQ(r.take_discarded(), 11u + 500u + 3u);
    EXPECT_EQ(r.take_discarded(), 0u);
}

TEST(LineReader, OverlongInOneAppend)
{
    LineReader r(10);
    std::string b;
    r.append(std::string(30, 'y') + "\nshort\n");
    ASSERT_TRUE(r.next_batch(b));
    EXPECT_EQ(b, "short\n");
    EXPECT_EQ(r.take_discarded(), 31u);
}

TEST(LineReader, DefaultLimitIsTheOldMaxCommandLength)
{
    LineReader r;
    EXPECT_EQ(r.limit(), 200000u);
    std::string b;
    // 300 KB with no newline, then commands: the commands still run.
    r.append("#" + std::string(300000, 'a'));
    r.append("\ntrick.var_send_once(\"x\")\n");
    ASSERT_TRUE(r.next_batch(b));
    EXPECT_EQ(b, "trick.var_send_once(\"x\")\n");
    EXPECT_EQ(r.take_discarded(), 300002u);
}

TEST(LineReader, BatchesAreAtMostTheLimit)
{
    LineReader r(20);
    std::string b;
    r.append("aaaaaaaa\nbbbbbbbb\ncccccccc\n"); // 27 bytes of whole lines
    ASSERT_TRUE(r.next_batch(b));
    EXPECT_EQ(b, "aaaaaaaa\nbbbbbbbb\n");
    ASSERT_TRUE(r.next_batch(b));
    EXPECT_EQ(b, "cccccccc\n");
}

// ---------------------------------------------------------------------------
// WriteQueue
// ---------------------------------------------------------------------------

TEST(WriteQueue, Bounded)
{
    WriteQueue q(10);
    EXPECT_TRUE(q.push("12345"));
    EXPECT_TRUE(q.push("1234"));
    EXPECT_FALSE(q.push("12")); // 11 > 10: refused whole
    EXPECT_EQ(q.size(), 9u);
    EXPECT_EQ(q.messages(), 2u);
    EXPECT_TRUE(q.push("1"));
    EXPECT_EQ(q.space(), 0u);
    EXPECT_TRUE(q.push("")); // nothing to add
}

TEST(WriteQueue, StreamConsumeAcrossMessages)
{
    WriteQueue q;
    q.push("abc");
    q.push("defg");
    EXPECT_EQ(q.front(), "abc");
    q.consume(2);
    EXPECT_EQ(q.front(), "c");
    EXPECT_EQ(q.size(), 5u);
    q.consume(3);
    EXPECT_EQ(q.front(), "fg");
    q.consume(2);
    EXPECT_TRUE(q.empty());
    EXPECT_EQ(q.size(), 0u);
}

TEST(WriteQueue, DatagramPop)
{
    WriteQueue q;
    q.push("one");
    q.push("two");
    q.consume(1);
    q.pop(); // the rest of "one"
    EXPECT_EQ(q.front(), "two");
    EXPECT_EQ(q.size(), 3u);
    q.pop();
    q.pop(); // on an empty queue: nothing
    EXPECT_TRUE(q.empty());
}
