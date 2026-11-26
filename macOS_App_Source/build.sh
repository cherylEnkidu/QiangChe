#!/bin/bash
set -e

echo "Compiling Swift code..."
MACOSX_DEPLOYMENT_TARGET=11.0 swiftc AutoEnterApp.swift -parse-as-library -o AutoEnterAppExecutable

echo "Creating App Bundle Structure..."
APP_DIR="../AutoEnterApp.app"
mkdir -p "$APP_DIR/Contents/MacOS"
mkdir -p "$APP_DIR/Contents/Resources"

echo "Moving files into bundle..."
mv AutoEnterAppExecutable "$APP_DIR/Contents/MacOS/AutoEnterApp"
cp wechat-rtt.sh "$APP_DIR/Contents/Resources/"
cp Info.plist "$APP_DIR/Contents/Info.plist"

codesign --force --sign - "$APP_DIR"

echo "Build complete! Your app is at $APP_DIR"
