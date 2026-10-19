// =====================================
// src/context/AppContext.tsx
// =====================================
import React, { createContext, useContext, useState } from "react";
import type { ReactNode } from "react";

interface AppContextType {
  isLoggedIn: boolean;
  setIsLoggedIn: (value: boolean) => void;
  username: string | null;
  setUsername: React.Dispatch<React.SetStateAction<string | null>>;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

export const useAppContext = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error("useAppContext must be used within an AppProvider");
  }
  return context;
};

export const AppProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [isLoggedIn, setIsLoggedInState] = useState<boolean>(() => {
    return localStorage.getItem("isLoggedIn") === "true";
  });
  const [username, setUsername] = useState<string | null>(() => {
    const stored = localStorage.getItem("username");
    return stored ? stored.replace(/"/g, "") : null;
  });

  const setIsLoggedIn = (value: boolean) => {
    setIsLoggedInState(value);
    localStorage.setItem("isLoggedIn", String(value));
    if (!value) {
      setUsername(null);
      localStorage.removeItem("username");
    }
  };

  const value = {
    isLoggedIn,
    setIsLoggedIn,
    username,
    setUsername,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
};
