import { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

type Lang = "EN" | "AR" | "FR";

type Dict = {
  greeting: string;
  attractPrompt: string;
  tapToStart: string;
  chooseLanguage: string;
  searchReadyPrompt: string;
  scopeBanner: string;
  noPersonalData: string;
  searchPlaceholder: string;
  searchButton: string;
  clearButton: string;
  poseCta: string;
  searchingStages: [string, string, string];
  quickChips: string[];
  askTitle: string;
  guideTitle: string;
  poseTitle: string;
  shareTitle: string;
  directAnswer: string;
  steps: string;
  mistakes: string;
  followupTitle: string;
  clarifyTitle: string;
  feedbackPrompt: string;
  thanksMessage: string;
  groundedLabel: string;
  limitedSources: string;
  generalDisclaimer: string;
  showMore: string;
  showLess: string;
  localSource: string;
  openPdf: string;
  poseTap: string;
  countdownToggle: string;
  moreDetails: string;
  sources: string;
  wizardTitle: string;
  checklistTitle: string;
  qrPlaceholder: string;
  poseFrame: string;
  countdown: string;
  watermark: string;
  checklistLoaded: string;
  checklistMissing: string;
  footerDisclaimer: string;
  headerTitle: string;
  modePlaceholder: string;
  languageLabel: string;
  homeSearchLabel: string;
  trendingTitle: string;
  trendingQuestions: string[];
  serviceUnavailable: string;
  tryAgain: string;
  chatPlaceholder: string;
  sendButton: string;
  tayyibTyping: string;
  feedbackHelpQuestion: string;
  feedbackMoreQuestion: string;
  feedbackYesThumb: string;
  feedbackNoThumb: string;
};

type LangContextValue = {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: Dict;
};

const DICT: Record<Lang, Dict> = {
  EN: {
    greeting: "Ask about Umrah steps, Procedure and Guidance",
    attractPrompt: "Official Umrah guidance, ready to help.",
    tapToStart: "Tap to begin",
    chooseLanguage: "Choose language",
    searchReadyPrompt: "Tap a topic or type a question",
    scopeBanner: "Umrah guidance only; not visa, legal, or medical advice. Check official authorities for critical decisions.",
    noPersonalData: "Do not enter personal data.",
    searchPlaceholder: "Search official guidance...",
    searchButton: "Search",
    clearButton: "Clear",
    poseCta: "Pose with Tayyib",
    searchingStages: ["Finding sources…", "Reading…", "Writing…"],
    quickChips: [
      "Umrah steps",
      "Miqat by air (الميقات)",
      "Ihram rules (الإحرام)",
      "Tawaf and Sa'i order (الطواف والسعي)"
    ],
    askTitle: "Ask (Chat + Sources)",
    guideTitle: "Guide (Wizard)",
    poseTitle: "Pose Mode",
    shareTitle: "Share Checklist",
    directAnswer: "Direct Answer",
    steps: "Steps",
    mistakes: "Common Mistakes",
    followupTitle: "Ask a follow-up",
    clarifyTitle: "Clarify your question",
    feedbackPrompt: "Rate this answer",
    thanksMessage: "Thanks for your feedback.",
    groundedLabel: "Grounded in official guidance",
    limitedSources: "Limited sources",
    generalDisclaimer: "General guidance (not sourced from the official PDFs). Please verify in Nusuk/official channels for critical details.",
    showMore: "Show more",
    showLess: "Show less",
    localSource: "Local source",
    openPdf: "Open PDF",
    poseTap: "Tap to change pose",
    countdownToggle: "Countdown toggle",
    moreDetails: "More Details",
    sources: "Sources",
    wizardTitle: "Wizard Steps",
    checklistTitle: "Checklist",
    qrPlaceholder: "QR placeholder",
    poseFrame: "Pose Frame",
    countdown: "Countdown",
    watermark: "ICHS Watermark",
    checklistLoaded: "Checklist loaded (placeholder)",
    checklistMissing: "No checklist payload detected",
    footerDisclaimer: "Informational guidance only. No legal or medical advice.",
    headerTitle: "Umrah AI Search",
    modePlaceholder: "Mode: Placeholder",
    languageLabel: "Language",
    homeSearchLabel: "Search",
    trendingTitle: "Trending questions",
    trendingQuestions: [
      "What are the steps of Umrah?",
      "What is miqat?",
      "How do I get a Nusuk permit?",
      "How to visit Rawdah?"
    ],
    serviceUnavailable: "Service unavailable. Please try again.",
    tryAgain: "Try again",
    chatPlaceholder: "Type your message...",
    sendButton: "Send",
    tayyibTyping: "Tayyib is typing...",
    feedbackHelpQuestion: "Did that answer help you?",
    feedbackMoreQuestion: "Is there anything else about Umrah I can help with?",
    feedbackYesThumb: "Yes",
    feedbackNoThumb: "No"
  },
  AR: {
    greeting: "اسأل عن خطوات العمرة والإجراءات والإرشادات",
    attractPrompt: "إرشادات رسمية للعمرة لمساعدتك.",
    tapToStart: "اضغط للبدء",
    chooseLanguage: "اختر اللغة",
    searchReadyPrompt: "اختر موضوعا أو اكتب سؤالا",
    scopeBanner: "إرشادات العمرة فقط؛ ليست مشورة قانونية أو طبية. راجع الجهات الرسمية للقرارات المهمة.",
    noPersonalData: "لا تدخل بيانات شخصية.",
    searchPlaceholder: "ابحث في الإرشادات الرسمية...",
    searchButton: "بحث",
    clearButton: "مسح",
    poseCta: "التقط صورة مع طيب",
    searchingStages: ["جار العثور على المصادر…", "جار القراءة…", "جار الكتابة…"],
    quickChips: [
      "خطوات العمرة",
      "الميقات جوًا (الميقات)",
      "أحكام الإحرام",
      "ترتيب الطواف والسعي"
    ],
    askTitle: "اسأل (محادثة + مصادر)",
    guideTitle: "الدليل (خطوات)",
    poseTitle: "وضعية التصوير",
    shareTitle: "مشاركة القائمة",
    directAnswer: "الإجابة المباشرة",
    steps: "الخطوات",
    mistakes: "أخطاء شائعة",
    followupTitle: "اسأل متابعة",
    clarifyTitle: "وضّح سؤالك",
    feedbackPrompt: "قيّم الإجابة",
    thanksMessage: "شكرا لملاحظاتك.",
    groundedLabel: "مستند إلى إرشادات رسمية",
    limitedSources: "مصادر محدودة",
    generalDisclaimer: "إرشادات عامة (غير مستندة إلى ملفات PDF الرسمية). يرجى التحقق من نسك/القنوات الرسمية للتفاصيل المهمة.",
    showMore: "عرض المزيد",
    showLess: "عرض أقل",
    localSource: "مصدر محلي",
    openPdf: "فتح الملف",
    poseTap: "اضغط لتغيير الوضعية",
    countdownToggle: "مؤقت العد التنازلي",
    moreDetails: "تفاصيل إضافية",
    sources: "المصادر",
    wizardTitle: "خطوات الإرشاد",
    checklistTitle: "قائمة التحقق",
    qrPlaceholder: "رمز QR (مكان مخصص)",
    poseFrame: "إطار التصوير",
    countdown: "العد التنازلي",
    watermark: "علامة ICHS",
    checklistLoaded: "تم تحميل القائمة (مكان مخصص)",
    checklistMissing: "لا توجد بيانات للقائمة",
    footerDisclaimer: "معلومات إرشادية فقط. لا توجد نصائح قانونية أو طبية.",
    headerTitle: "بحث العمرة بالذكاء الاصطناعي",
    modePlaceholder: "الوضع: مكان مخصص",
    languageLabel: "اللغة",
    homeSearchLabel: "بحث",
    trendingTitle: "أسئلة شائعة",
    trendingQuestions: [
      "ما خطوات العمرة؟",
      "ما هو الميقات؟",
      "كيف أحصل على تصريح نسك؟",
      "كيف أزور الروضة الشريفة؟"
    ],
    serviceUnavailable: "الخدمة غير متاحة حاليا. حاول مرة أخرى.",
    tryAgain: "حاول مرة أخرى",
    chatPlaceholder: "اكتب رسالتك...",
    sendButton: "إرسال",
    tayyibTyping: "طيّب يكتب...",
    feedbackHelpQuestion: "هل كانت هذه الإجابة مفيدة؟",
    feedbackMoreQuestion: "هل هناك أي شيء آخر عن العمرة يمكنني مساعدتك به؟",
    feedbackYesThumb: "نعم",
    feedbackNoThumb: "لا"
  },
  FR: {
    greeting: "Posez des questions sur les étapes, procédures et conseils de la Omra",
    attractPrompt: "Guidance officielle pour la Omra, prête a aider.",
    tapToStart: "Touchez pour commencer",
    chooseLanguage: "Choisir la langue",
    searchReadyPrompt: "Touchez un sujet ou saisissez une question",
    scopeBanner: "Guidance Omra uniquement; pas de conseils visa, juridiques ou medicaux. Consultez les autorites officielles.",
    noPersonalData: "N'entrez aucune donnee personnelle.",
    searchPlaceholder: "Rechercher une guidance officielle...",
    searchButton: "Rechercher",
    clearButton: "Effacer",
    poseCta: "Pose avec Tayyib",
    searchingStages: ["Recherche des sources…", "Lecture…", "Redaction…"],
    quickChips: [
      "Etapes de la Omra",
      "Miqat par avion (الميقات)",
      "Regles de l'ihram (الإحرام)",
      "Ordre Tawaf et Sa'i (الطواف والسعي)"
    ],
    askTitle: "Demander (Chat + Sources)",
    guideTitle: "Guide (Assistant)",
    poseTitle: "Mode Pose",
    shareTitle: "Partager la checklist",
    directAnswer: "Reponse directe",
    steps: "Etapes",
    mistakes: "Erreurs courantes",
    followupTitle: "Question de suivi",
    clarifyTitle: "Precisez votre question",
    feedbackPrompt: "Notez cette reponse",
    thanksMessage: "Merci pour votre avis.",
    groundedLabel: "Fonde sur des sources officielles",
    limitedSources: "Sources limitees",
    generalDisclaimer: "Conseils generaux (non issus des PDF officiels). Verifiez via Nusuk/canaux officiels pour les details critiques.",
    showMore: "Afficher plus",
    showLess: "Afficher moins",
    localSource: "Source locale",
    openPdf: "Ouvrir le PDF",
    poseTap: "Touchez pour changer la pose",
    countdownToggle: "Basculer le compte a rebours",
    moreDetails: "Plus de details",
    sources: "Sources",
    wizardTitle: "Etapes du guide",
    checklistTitle: "Checklist",
    qrPlaceholder: "Zone QR (placeholder)",
    poseFrame: "Cadre de pose",
    countdown: "Compte a rebours",
    watermark: "Filigrane ICHS",
    checklistLoaded: "Checklist chargee (placeholder)",
    checklistMissing: "Aucune donnees de checklist",
    footerDisclaimer: "Informations uniquement. Pas de conseils juridiques ou medicaux.",
    headerTitle: "Recherche IA Omra",
    modePlaceholder: "Mode : placeholder",
    languageLabel: "Langue",
    homeSearchLabel: "Recherche",
    trendingTitle: "Questions tendances",
    trendingQuestions: [
      "Quelles sont les etapes de la Omra?",
      "Qu'est-ce que le miqat?",
      "Comment obtenir un permis Nusuk?",
      "Visiter la Rawdah"
    ],
    serviceUnavailable: "Service indisponible. Veuillez reessayer.",
    tryAgain: "Reessayer",
    chatPlaceholder: "Tapez votre message...",
    sendButton: "Envoyer",
    tayyibTyping: "Tayyib ecrit...",
    feedbackHelpQuestion: "Cette reponse vous a-t-elle aide ?",
    feedbackMoreQuestion: "Y a-t-il autre chose sur la Omra avec laquelle je peux vous aider ?",
    feedbackYesThumb: "Oui",
    feedbackNoThumb: "Non"
  }
};

const LangContext = createContext<LangContextValue | null>(null);

const STORAGE_KEY = "kiosk_lang";

export function LangProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => {
    const stored = sessionStorage.getItem(STORAGE_KEY) as Lang | null;
    return stored ?? "EN";
  });

  useEffect(() => {
    sessionStorage.setItem(STORAGE_KEY, lang);
    const dir = lang === "AR" ? "rtl" : "ltr";
    document.documentElement.setAttribute("dir", dir);
    document.body.setAttribute("dir", dir);
  }, [lang]);

  const value = useMemo<LangContextValue>(
    () => ({
      lang,
      setLang: setLangState,
      t: DICT[lang]
    }),
    [lang]
  );

  return <LangContext.Provider value={value}>{children}</LangContext.Provider>;
}

export function useLang() {
  const ctx = useContext(LangContext);
  if (!ctx) {
    throw new Error("useLang must be used within LangProvider");
  }
  return ctx;
}
