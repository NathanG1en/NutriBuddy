import { useState, useEffect, useRef } from 'react';

export const useSpeechRecognition = () => {
    const [isListening, setIsListening] = useState(false);
    const [transcript, setTranscript] = useState('');
    const [isSupported, setIsSupported] = useState(true);

    const recognitionRef = useRef<any>(null);

    useEffect(() => {
        if (!('webkitSpeechRecognition' in window)) {
            setIsSupported(false);
            return;
        }

        // Initialize Speech Recognition
        const recognition = new (window as any).webkitSpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.lang = 'en-US';

        recognition.onstart = () => {
            setIsListening(true);
        };

        recognition.onend = () => {
            setIsListening(false);
        };

        recognition.onresult = (event: any) => {
            const text = event.results[0][0].transcript;
            setTranscript(text);
        };

        recognitionRef.current = recognition;
    }, []);

    const startListening = () => {
        setTranscript('');
        recognitionRef.current?.start();
    };

    const stopListening = () => {
        recognitionRef.current?.stop();
    };

    return {
        isListening,
        transcript,
        startListening,
        stopListening,
        isSupported
    };
};
