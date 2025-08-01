#!/usr/bin/env python3
"""
Simple script to view the contents of the BeatSync database
"""
import sqlite3
import json
from datetime import datetime

def view_database():
    conn = sqlite3.connect('beatsync.db')
    cursor = conn.cursor()
    
    print("=" * 60)
    print("BEATSYNC DATABASE CONTENTS")
    print("=" * 60)
    
    # Queue Items
    print("\n📀 QUEUE ITEMS:")
    print("-" * 40)
    cursor.execute("SELECT * FROM queue_items ORDER BY timestamp")
    queue_items = cursor.fetchall()
    
    if queue_items:
        for item in queue_items:
            print(f"ID: {item[0]}")
            print(f"Track: {item[2]}")
            print(f"URI: {item[1]}")
            print(f"Added: {item[3]}")
            print("-" * 40)
    else:
        print("No items in queue")
    
    # Votes
    print("\n👍 VOTES:")
    print("-" * 40)
    cursor.execute("SELECT track_uri, vote_type, COUNT(*) FROM votes GROUP BY track_uri, vote_type")
    votes = cursor.fetchall()
    
    if votes:
        vote_summary = {}
        for vote in votes:
            uri = vote[0]
            if uri not in vote_summary:
                vote_summary[uri] = {'up': 0, 'down': 0}
            vote_summary[uri][vote[1]] = vote[2]
        
        for uri, counts in vote_summary.items():
            print(f"Track: {uri}")
            print(f"  👍 Up votes: {counts['up']}")
            print(f"  👎 Down votes: {counts['down']}")
            print(f"  📊 Net score: {counts['up'] - counts['down']}")
            print("-" * 40)
    else:
        print("No votes cast")
    
    # Chat Messages
    print("\n💬 CHAT MESSAGES:")
    print("-" * 40)
    cursor.execute("SELECT * FROM chat_messages ORDER BY timestamp DESC LIMIT 10")
    messages = cursor.fetchall()
    
    if messages:
        for msg in messages:
            print(f"[{msg[3]}] {msg[1]}: {msg[2]}")
        print(f"\n(Showing last {len(messages)} messages)")
    else:
        print("No chat messages")
    
    # Database stats
    print("\n📊 DATABASE STATISTICS:")
    print("-" * 40)
    cursor.execute("SELECT COUNT(*) FROM queue_items")
    queue_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM votes")
    vote_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM chat_messages")
    chat_count = cursor.fetchone()[0]
    
    print(f"Total queue items: {queue_count}")
    print(f"Total votes: {vote_count}")
    print(f"Total chat messages: {chat_count}")
    
    conn.close()
    print("\n" + "=" * 60)

if __name__ == "__main__":
    view_database()
