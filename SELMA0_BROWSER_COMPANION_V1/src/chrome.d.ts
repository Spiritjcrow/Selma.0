// Minimal Chromium MV3 API declarations for an isolated build.
declare const chrome: {
  runtime: {
    id: string;
    onMessage: {
      addListener(cb: (message: unknown, sender: { id?: string }, sendResponse: (response: unknown) => void) => boolean | void): void;
    };
    sendMessage(message: unknown): Promise<unknown>;
  };
  permissions: {
    request(options: { origins: string[] }): Promise<boolean>;
    remove(options: { origins: string[] }): Promise<boolean>;
  };
  storage: {
    session: {
      get(keys: string[]): Promise<Record<string, unknown>>;
      set(values: Record<string, unknown>): Promise<void>;
      remove(keys: string[]): Promise<void>;
    };
  };
};
