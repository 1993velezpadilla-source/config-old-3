#include <jni.h>
#include <SDL.h>
#include <SDL_system.h>
#include <string.h>

static JNIEnv *Xziel_Env(void)
{
    return (JNIEnv *)SDL_AndroidGetJNIEnv();
}

static jobject Xziel_Activity(JNIEnv *env)
{
    if (!env) return NULL;
    return SDL_AndroidGetActivity();
}

static jmethodID Xziel_Method(JNIEnv *env, jobject activity,
    const char *name, const char *signature)
{
    jclass cls;
    jmethodID method;

    if (!env || !activity) return NULL;
    cls = (*env)->GetObjectClass(env, activity);
    if (!cls) return NULL;
    method = (*env)->GetMethodID(env, cls, name, signature);
    (*env)->DeleteLocalRef(env, cls);
    return method;
}

static void Xziel_ClearException(JNIEnv *env)
{
    if (env && (*env)->ExceptionCheck(env))
        (*env)->ExceptionClear(env);
}

void Xziel_Android_OpenMultiplayer(void)
{
    JNIEnv *env = Xziel_Env();
    jobject activity = Xziel_Activity(env);
    jmethodID method = Xziel_Method(env, activity, "xzielOpenMultiplayer", "()V");

    if (method)
        (*env)->CallVoidMethod(env, activity, method);
    if (activity)
        (*env)->DeleteLocalRef(env, activity);
    Xziel_ClearException(env);
}

int Xziel_Android_OnlineActive(void)
{
    JNIEnv *env = Xziel_Env();
    jobject activity = Xziel_Activity(env);
    jmethodID method = Xziel_Method(env, activity, "xzielOnlineActive", "()Z");
    jboolean result = JNI_FALSE;

    if (method)
        result = (*env)->CallBooleanMethod(env, activity, method);
    if (activity)
        (*env)->DeleteLocalRef(env, activity);
    Xziel_ClearException(env);
    return result == JNI_TRUE;
}

int Xziel_Android_GameHasPacket(int localPort)
{
    JNIEnv *env = Xziel_Env();
    jobject activity = Xziel_Activity(env);
    jmethodID method = Xziel_Method(env, activity, "xzielGameHasPacket", "(I)Z");
    jboolean result = JNI_FALSE;

    if (method)
        result = (*env)->CallBooleanMethod(env, activity, method, (jint)localPort);
    if (activity)
        (*env)->DeleteLocalRef(env, activity);
    Xziel_ClearException(env);
    return result == JNI_TRUE;
}

int Xziel_Android_GameSend(const unsigned char *data, int len,
    int destinationSlot, int sourcePort, int destinationPort)
{
    JNIEnv *env = Xziel_Env();
    jobject activity = Xziel_Activity(env);
    jmethodID method;
    jbyteArray array = NULL;
    jboolean result = JNI_FALSE;

    if (!env || !activity || !data || len <= 0)
        goto done;

    method = Xziel_Method(env, activity, "xzielGameSend", "([BIII)Z");
    if (!method)
        goto done;

    array = (*env)->NewByteArray(env, len);
    if (!array)
        goto done;

    (*env)->SetByteArrayRegion(env, array, 0, len, (const jbyte *)data);
    result = (*env)->CallBooleanMethod(
        env, activity, method, array,
        (jint)destinationSlot, (jint)sourcePort, (jint)destinationPort);

done:
    if (array)
        (*env)->DeleteLocalRef(env, array);
    if (activity)
        (*env)->DeleteLocalRef(env, activity);
    Xziel_ClearException(env);
    return result == JNI_TRUE;
}

int Xziel_Android_GamePoll(int localPort, unsigned char *out, int maxLen,
    int *sourceSlot, int *sourcePort)
{
    JNIEnv *env = Xziel_Env();
    jobject activity = Xziel_Activity(env);
    jmethodID method;
    jbyteArray array = NULL;
    jsize length;
    jbyte meta[3];
    int payloadLen = 0;

    if (!env || !activity || !out || maxLen <= 0)
        goto done;

    method = Xziel_Method(env, activity, "xzielGamePoll", "(I)[B");
    if (!method)
        goto done;

    array = (jbyteArray)(*env)->CallObjectMethod(env, activity, method, (jint)localPort);
    if (!array || (*env)->ExceptionCheck(env))
        goto done;

    length = (*env)->GetArrayLength(env, array);
    if (length <= 3)
        goto done;

    payloadLen = (int)length - 3;
    if (payloadLen > maxLen) {
        payloadLen = 0;
        goto done;
    }

    (*env)->GetByteArrayRegion(env, array, 0, 3, meta);
    if (sourceSlot)
        *sourceSlot = ((unsigned char)meta[0]);
    if (sourcePort)
        *sourcePort = (((unsigned char)meta[1]) << 8) |
                      ((unsigned char)meta[2]);

    (*env)->GetByteArrayRegion(env, array, 3, payloadLen, (jbyte *)out);

done:
    if (array)
        (*env)->DeleteLocalRef(env, array);
    if (activity)
        (*env)->DeleteLocalRef(env, activity);
    Xziel_ClearException(env);
    return payloadLen;
}

int Xziel_Android_OnlinePollCommand(char *out, int outSize)
{
    JNIEnv *env = Xziel_Env();
    jobject activity = Xziel_Activity(env);
    jmethodID method;
    jstring value = NULL;
    const char *utf = NULL;
    int copied = 0;

    if (!env || !activity || !out || outSize < 2)
        goto done;

    out[0] = 0;
    method = Xziel_Method(env, activity, "xzielOnlinePollCommand",
        "()Ljava/lang/String;");
    if (!method)
        goto done;

    value = (jstring)(*env)->CallObjectMethod(env, activity, method);
    if (!value || (*env)->ExceptionCheck(env))
        goto done;

    utf = (*env)->GetStringUTFChars(env, value, NULL);
    if (!utf)
        goto done;

    if (*utf) {
        strncpy(out, utf, (size_t)outSize - 1);
        out[outSize - 1] = 0;
        copied = 1;
    }

done:
    if (utf && value)
        (*env)->ReleaseStringUTFChars(env, value, utf);
    if (value)
        (*env)->DeleteLocalRef(env, value);
    if (activity)
        (*env)->DeleteLocalRef(env, activity);
    Xziel_ClearException(env);
    return copied;
}


void Xziel_Android_OnlineReportEngineState(int serverActive, int clientConnected,
    int signon, const char *map)
{
    JNIEnv *env = Xziel_Env();
    jobject activity = Xziel_Activity(env);
    jmethodID method;
    jstring mapString = NULL;

    if (!env || !activity)
        goto done;

    method = Xziel_Method(env, activity, "xzielOnlineEngineState",
        "(ZZILjava/lang/String;)V");
    if (!method)
        goto done;

    mapString = (*env)->NewStringUTF(env, map ? map : "");
    if (!mapString)
        goto done;

    (*env)->CallVoidMethod(env, activity, method,
        serverActive ? JNI_TRUE : JNI_FALSE,
        clientConnected ? JNI_TRUE : JNI_FALSE,
        (jint)signon, mapString);

done:
    if (mapString)
        (*env)->DeleteLocalRef(env, mapString);
    if (activity)
        (*env)->DeleteLocalRef(env, activity);
    Xziel_ClearException(env);
}

void Xziel_Android_OnlineLeaveRoom(void)
{
    JNIEnv *env = Xziel_Env();
    jobject activity = Xziel_Activity(env);
    jmethodID method = Xziel_Method(env, activity, "xzielLeaveMultiplayer", "()V");

    if (method)
        (*env)->CallVoidMethod(env, activity, method);
    if (activity)
        (*env)->DeleteLocalRef(env, activity);
    Xziel_ClearException(env);
}


void Xziel_Android_VoiceUpdatePosition(float x, float y, float z)
{
    JNIEnv *env = Xziel_Env();
    jobject activity = Xziel_Activity(env);
    jmethodID method = Xziel_Method(env, activity, "xzielVoiceUpdatePosition", "(FFF)V");

    if (method)
        (*env)->CallVoidMethod(env, activity, method, (jfloat)x, (jfloat)y, (jfloat)z);
    if (activity)
        (*env)->DeleteLocalRef(env, activity);
    Xziel_ClearException(env);
}

void Xziel_Android_OnlinePauseVoice(int visible)
{
    JNIEnv *env = Xziel_Env();
    jobject activity = Xziel_Activity(env);
    jmethodID method = Xziel_Method(env, activity, "xzielOnlinePauseVoice", "(Z)V");

    if (method)
        (*env)->CallVoidMethod(env, activity, method,
            visible ? JNI_TRUE : JNI_FALSE);
    if (activity)
        (*env)->DeleteLocalRef(env, activity);
    Xziel_ClearException(env);
}


void Xziel_Android_CiRemoteEntity(int slot, float x, float y, float z,
    int frame, float yaw)
{
    JNIEnv *env = Xziel_Env();
    jobject activity = Xziel_Activity(env);
    jmethodID method = Xziel_Method(env, activity, "xzielCiRemoteEntity",
        "(IFFFIF)V");

    if (method)
        (*env)->CallVoidMethod(env, activity, method,
            (jint)slot, (jfloat)x, (jfloat)y, (jfloat)z,
            (jint)frame, (jfloat)yaw);
    if (activity)
        (*env)->DeleteLocalRef(env, activity);
    Xziel_ClearException(env);
}


void Xziel_Android_CiSoundEvent(int ent, int channel, const char *name,
    float x, float y, float z)
{
    JNIEnv *env = Xziel_Env();
    jobject activity = Xziel_Activity(env);
    jmethodID method;
    jstring soundName = NULL;

    if (!env || !activity)
        goto done;

    method = Xziel_Method(env, activity, "xzielCiSoundEvent",
        "(IILjava/lang/String;FFF)V");
    if (!method)
        goto done;

    soundName = (*env)->NewStringUTF(env, name ? name : "");
    if (!soundName)
        goto done;

    (*env)->CallVoidMethod(env, activity, method,
        (jint)ent, (jint)channel, soundName,
        (jfloat)x, (jfloat)y, (jfloat)z);

done:
    if (soundName)
        (*env)->DeleteLocalRef(env, soundName);
    if (activity)
        (*env)->DeleteLocalRef(env, activity);
    Xziel_ClearException(env);
}
