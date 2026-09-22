package com.monopoliorecords.panelplayer;

public final class Channel {
    public final String name;
    public final String streamId;
    public Channel(String name, String streamId) { this.name = name; this.streamId = streamId; }
    @Override public String toString() { return name; }
}
