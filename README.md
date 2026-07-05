# Restaurant Management System

A full-stack restaurant management system with a web-based backend and a companion Android mobile app, built to handle end-to-end restaurant operations — from order taking to payment processing and sales analytics.


## Overview

This project simulates a real-world restaurant workflow with role-based access for four types of staff: Manager, Chef, Cashier, and Waiter. Each role has a dedicated dashboard tailored to their responsibilities, backed by a shared order and table management system.


## Features

### 🔐 Role-Based Dashboards

  * Manager — full oversight: menu management, waiter accounts, sales analytics, and reporting

  * Chef — live order queue (pending → preparing → served)

  * Cashier — pending bills, payment processing, receipt generation

  * Waiter — table assignment, order creation, order tracking


### 📊 Sales & Analytics


  * Daily, weekly, monthly, and custom date-range sales reports

  * Revenue breakdown by menu category

  * Top-selling dishes tracked by order count and revenue

  * Real-time stats: today's sales, total orders, active waiters, average bill

### 🍽️ Order & Table Management


  * Live table status tracking (available/occupied) with occupancy duration

  * Order lifecycle management (pending, preparing, served, completed)

  * Bill request flow separate from order-served status

  * Itemized receipt generation with tax and discount computation

### 🕒 Localization

  * Philippine Standard Time (UTC+8) used throughout for accurate order and payment timestamps


### 📱 Mobile Companion App

  * Android app (/mobile-app) extending core functionality to mobile devices


## Tech Stack

  ### Backend (Web)
    * Python, Flask
    * SQLite
    * Session-based authentication

  ### Mobile
    * Android Studio (Java/Kotlin)
