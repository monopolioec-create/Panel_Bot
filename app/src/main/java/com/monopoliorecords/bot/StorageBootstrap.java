package com.monopoliorecords.bot;

import android.content.Context;
import java.io.File;

public final class StorageBootstrap {
    private StorageBootstrap() {}
    public static File prepare(Context c) throws Exception {
        File dir = new File(c.getFilesDir(), "wuzapi");
        File db = new File(dir, "dbdata");
        if (!db.exists() && !db.mkdirs()) throw new Exception("No se pudo crear almacenamiento interno");
        return dir;
    }
}
