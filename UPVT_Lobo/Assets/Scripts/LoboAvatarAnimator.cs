using System;
using System.Collections;
using UnityEngine;

/// <summary>Traduce los metadatos de la API a clips del esqueleto del Lobo.</summary>
public sealed class LoboAvatarAnimator : MonoBehaviour
{
    [SerializeField] private Animator animator;
    [SerializeField] private Animation legacyAnimation;
    [SerializeField, Min(0.5f)] private float oneShotDuration = 2.2f;
    private Coroutine resetRoutine;

    public void SetAnimator(Animator value) => animator = value;
    public void SetLegacyAnimation(Animation value) => legacyAnimation = value;

    public void PlayReply(LoboChatReply reply)
    {
        if (reply == null) return;
        var requested = MapClip(reply.animacion, reply.emocion, reply.accion_avatar);
        if (!PlayClip(requested))
        {
            requested = "Hablar";
            PlayClip(requested);
        }
        if (resetRoutine != null) StopCoroutine(resetRoutine);
        resetRoutine = StartCoroutine(ReturnToIdle(Mathf.Max(oneShotDuration, GetClipDuration(requested))));
    }

    private bool PlayClip(string clipName)
    {
        if (animator != null && animator.runtimeAnimatorController != null)
        {
            var hash = Animator.StringToHash(clipName);
            if (animator.HasState(0, hash))
            {
                animator.Play(hash, 0, 0f);
                return true;
            }
        }
        return legacyAnimation != null && legacyAnimation.GetClip(clipName) != null && legacyAnimation.Play(clipName);
    }

    private float GetClipDuration(string clipName)
    {
        if (legacyAnimation != null)
        {
            var legacyClip = legacyAnimation.GetClip(clipName);
            if (legacyClip != null) return legacyClip.length;
        }

        var controller = animator != null ? animator.runtimeAnimatorController : null;
        if (controller != null)
        {
            foreach (var clip in controller.animationClips)
                if (clip != null && string.Equals(clip.name, clipName, StringComparison.OrdinalIgnoreCase))
                    return clip.length;
        }

        return oneShotDuration;
    }

    private static string MapClip(string animation, string emotion, string action)
    {
        var metadata = ((animation ?? "") + " " + (emotion ?? "") + " " + (action ?? "")).ToLowerInvariant();
        if (metadata.Contains("salud") || metadata.Contains("greet") || metadata.Contains("hola")) return "Saludo";
        if (metadata.Contains("celebr") || metadata.Contains("festej") || metadata.Contains("bail")) return "Celebrar";
        if (metadata.Contains("pens") || metadata.Contains("think") || metadata.Contains("duda")) return "Pensar";
        return "Hablar";
    }

    private IEnumerator ReturnToIdle(float duration)
    {
        yield return new WaitForSeconds(duration);
        PlayClip("Idle");
        resetRoutine = null;
    }
}
