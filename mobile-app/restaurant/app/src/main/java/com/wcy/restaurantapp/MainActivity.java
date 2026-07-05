package com.wcy.restaurantapp;

import android.Manifest;
import android.annotation.SuppressLint;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.provider.MediaStore;
import android.util.Log;
import android.webkit.ConsoleMessage;
import android.webkit.JavascriptInterface;
import android.webkit.PermissionRequest;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import androidx.activity.OnBackPressedCallback;
import androidx.annotation.NonNull;
import androidx.annotation.RequiresApi;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;
import androidx.core.content.FileProvider;

import java.io.File;
import java.io.IOException;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.List;

public class MainActivity extends AppCompatActivity {
    private WebView webView;
    private ValueCallback<Uri[]> filePathCallback;
    private Uri cameraPhotoUri;
    private static final int CAMERA_PERMISSION_CODE = 100;
    private static final int FILE_CHOOSER_RESULT_CODE = 200;
    private static final int CAMERA_RESULT_CODE = 300;
    private static final String TAG = "RestaurantApp";

    private OnBackPressedCallback backPressedCallback;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        webView = findViewById(R.id.webView);

        // Configure WebView
        WebSettings webSettings = webView.getSettings();
        webSettings.setJavaScriptEnabled(true);
        webSettings.setDomStorageEnabled(true);
        webSettings.setDatabaseEnabled(true);
        webSettings.setAllowFileAccess(true);
        webSettings.setAllowContentAccess(true);
        webSettings.setAllowFileAccessFromFileURLs(true);
        webSettings.setAllowUniversalAccessFromFileURLs(true);
        webSettings.setMediaPlaybackRequiresUserGesture(false);
        webSettings.setJavaScriptCanOpenWindowsAutomatically(true);
        webSettings.setGeolocationEnabled(true);

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            webSettings.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        }

        // WebView navigation
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, String url) {
                view.loadUrl(url);
                return true;
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                Log.d(TAG, "Page loaded: " + url);

                // Inject JavaScript to help debug camera issues
                injectDebugJavaScript();
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView webView,
                                             ValueCallback<Uri[]> filePathCallback,
                                             FileChooserParams fileChooserParams) {

                Log.d(TAG, "onShowFileChooser triggered");
                if (fileChooserParams != null && fileChooserParams.getAcceptTypes() != null && fileChooserParams.getAcceptTypes().length > 0) {
                    Log.d(TAG, "Accept types: " + fileChooserParams.getAcceptTypes()[0]);
                }

                // Clear any previous callback
                if (MainActivity.this.filePathCallback != null) {
                    MainActivity.this.filePathCallback.onReceiveValue(null);
                }

                // Store the new callback
                MainActivity.this.filePathCallback = filePathCallback;

                // Check if we have camera permission
                if (ContextCompat.checkSelfPermission(MainActivity.this,
                        Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {

                    Log.d(TAG, "Requesting camera permission...");
                    ActivityCompat.requestPermissions(MainActivity.this,
                            new String[]{Manifest.permission.CAMERA},
                            CAMERA_PERMISSION_CODE);
                } else {
                    Log.d(TAG, "Camera permission already granted, showing chooser");
                    showImageChooser();
                }
                return true;
            }

            @RequiresApi(api = Build.VERSION_CODES.LOLLIPOP)
            @Override
            public void onPermissionRequest(PermissionRequest request) {
                String[] resources = request.getResources();
                String resourcesStr = "";
                if (resources != null) {
                    for (String resource : resources) {
                        resourcesStr += resource + ", ";
                    }
                }
                Log.d(TAG, "Granting WebView permissions: " + resourcesStr);
                // Grant all requested permissions to WebView
                request.grant(request.getResources());
            }

            @Override
            @RequiresApi(api = Build.VERSION_CODES.LOLLIPOP)
            public void onPermissionRequestCanceled(PermissionRequest request) {
                Log.w(TAG, "WebView permission request cancelled");
                Toast.makeText(MainActivity.this,
                        "Camera permission required", Toast.LENGTH_SHORT).show();
            }

            @Override
            public boolean onConsoleMessage(ConsoleMessage consoleMessage) {
                Log.d("WebViewConsole",
                        consoleMessage.message() + " at " +
                                consoleMessage.sourceId() + ":" +
                                consoleMessage.lineNumber());
                return true;
            }

            @Override
            public void onGeolocationPermissionsShowPrompt(String origin,
                                                           android.webkit.GeolocationPermissions.Callback callback) {
                callback.invoke(origin, true, false);
            }
        });

        // JavaScript interface
        webView.addJavascriptInterface(new WebAppInterface(), "Android");

        // Back gesture
        backPressedCallback = new OnBackPressedCallback(true) {
            @Override
            public void handleOnBackPressed() {
                if (webView.canGoBack()) {
                    webView.goBack();
                } else {
                    setEnabled(false);
                    getOnBackPressedDispatcher().onBackPressed();
                }
            }
        };
        getOnBackPressedDispatcher().addCallback(this, backPressedCallback);

        // Request all permissions on startup
        requestAllPermissions();

        // Load URL
        String serverUrl = " https://stuffing-deceit-handoff.ngrok-free.dev ";
        Log.d(TAG, "Loading URL: " + serverUrl);
        webView.loadUrl(serverUrl);
    }

    private void showImageChooser() {
        Log.d(TAG, "showImageChooser");

        // Create camera intent
        Intent cameraIntent = new Intent(MediaStore.ACTION_IMAGE_CAPTURE);

        // Create file for camera
        if (cameraIntent.resolveActivity(getPackageManager()) != null) {
            try {
                File photoFile = createImageFile();
                if (photoFile != null) {
                    cameraPhotoUri = FileProvider.getUriForFile(this,
                            getApplicationContext().getPackageName() + ".fileprovider",
                            photoFile);

                    Log.d(TAG, "Camera photo URI created: " + cameraPhotoUri);

                    // Grant temporary read permission to the camera app
                    List<ResolveInfo> resolvedIntentActivities = getPackageManager()
                            .queryIntentActivities(cameraIntent, PackageManager.MATCH_DEFAULT_ONLY);

                    for (ResolveInfo resolvedIntentInfo : resolvedIntentActivities) {
                        String packageName = resolvedIntentInfo.activityInfo.packageName;
                        grantUriPermission(packageName, cameraPhotoUri,
                                Intent.FLAG_GRANT_WRITE_URI_PERMISSION |
                                        Intent.FLAG_GRANT_READ_URI_PERMISSION);
                    }

                    cameraIntent.putExtra(MediaStore.EXTRA_OUTPUT, cameraPhotoUri);
                    cameraIntent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                    cameraIntent.addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
                }
            } catch (IOException ex) {
                Log.e(TAG, "Error creating image file", ex);
                Toast.makeText(this, "Error creating image file", Toast.LENGTH_SHORT).show();
                cameraPhotoUri = null;
            }
        } else {
            Log.w(TAG, "No camera app available");
            Toast.makeText(this, "No camera app found", Toast.LENGTH_SHORT).show();
            cameraPhotoUri = null;
        }

        // Create gallery intent
        Intent galleryIntent = new Intent(Intent.ACTION_GET_CONTENT);
        galleryIntent.addCategory(Intent.CATEGORY_OPENABLE);
        galleryIntent.setType("image/*");
        galleryIntent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);

        // Also support multiple content sources
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.KITKAT) {
            galleryIntent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, false);
        }

        // Create chooser intent
        Intent chooserIntent;

        if (cameraPhotoUri != null && cameraIntent.resolveActivity(getPackageManager()) != null) {
            // Both camera and gallery available
            chooserIntent = Intent.createChooser(galleryIntent, "Select Image Source");
            chooserIntent.putExtra(Intent.EXTRA_INITIAL_INTENTS, new Intent[]{cameraIntent});
            Log.d(TAG, "Chooser with both camera and gallery");
        } else {
            // Only gallery available
            chooserIntent = Intent.createChooser(galleryIntent, "Select Image");
            Log.d(TAG, "Chooser with only gallery");
        }

        try {
            startActivityForResult(chooserIntent, FILE_CHOOSER_RESULT_CODE);
        } catch (Exception e) {
            Log.e(TAG, "Error starting chooser", e);
            Toast.makeText(this, "Error opening file chooser: " + e.getMessage(),
                    Toast.LENGTH_SHORT).show();

            if (filePathCallback != null) {
                filePathCallback.onReceiveValue(null);
                filePathCallback = null;
            }
        }
    }

    // Request all permissions
    private void requestAllPermissions() {
        String[] permissions;

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            // Android 13+ uses different permissions
            permissions = new String[]{
                    Manifest.permission.CAMERA,
                    Manifest.permission.RECORD_AUDIO,
                    Manifest.permission.READ_MEDIA_IMAGES,
                    Manifest.permission.READ_MEDIA_VIDEO
            };
        } else {
            permissions = new String[]{
                    Manifest.permission.CAMERA,
                    Manifest.permission.RECORD_AUDIO,
                    Manifest.permission.READ_EXTERNAL_STORAGE,
                    Manifest.permission.WRITE_EXTERNAL_STORAGE
            };
        }

        ActivityCompat.requestPermissions(this, permissions, 123);
        Log.d(TAG, "Requested all permissions");
    }

    // JavaScript interface
    public class WebAppInterface {
        @JavascriptInterface
        public void showToast(String message) {
            Toast.makeText(MainActivity.this, message, Toast.LENGTH_SHORT).show();
        }

        @JavascriptInterface
        public String getDeviceInfo() {
            return "Android " + Build.VERSION.RELEASE + " | WebView";
        }

        @JavascriptInterface
        public boolean hasCameraPermission() {
            boolean hasPermission = ContextCompat.checkSelfPermission(MainActivity.this,
                    Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED;
            Log.d(TAG, "JavaScript checking camera permission: " + hasPermission);
            return hasPermission;
        }

        @JavascriptInterface
        public void testCamera() {
            Log.d(TAG, "JavaScript testing camera");
            runOnUiThread(() -> {
                Toast.makeText(MainActivity.this, "Testing camera from JavaScript", Toast.LENGTH_SHORT).show();
                // Trigger camera from JavaScript
                showImageChooser();
            });
        }

        @JavascriptInterface
        public void requestCameraPermission() {
            Log.d(TAG, "JavaScript requesting camera permission");
            runOnUiThread(() -> {
                ActivityCompat.requestPermissions(MainActivity.this,
                        new String[]{Manifest.permission.CAMERA},
                        CAMERA_PERMISSION_CODE);
            });
        }
    }

    // Create image file for camera
    private File createImageFile() throws IOException {
        @SuppressLint("SimpleDateFormat")
        String timeStamp = new SimpleDateFormat("yyyyMMdd_HHmmss").format(new Date());
        String imageFileName = "restaurant_" + timeStamp + "_";

        File storageDir = getExternalFilesDir(Environment.DIRECTORY_PICTURES);
        if (storageDir == null) {
            storageDir = getFilesDir();
        }

        // Create directory if it doesn't exist
        if (!storageDir.exists()) {
            boolean created = storageDir.mkdirs();
            Log.d(TAG, "Storage directory created: " + created);
        }

        File imageFile = File.createTempFile(
                imageFileName,
                ".jpg",
                storageDir
        );

        Log.d(TAG, "Image file created at: " + imageFile.getAbsolutePath());
        return imageFile;
    }

    // Handle permission results
    @Override
    public void onRequestPermissionsResult(int requestCode,
                                           @NonNull String[] permissions,
                                           @NonNull int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);

        Log.d(TAG, "Permission result for request: " + requestCode);

        if (requestCode == CAMERA_PERMISSION_CODE) {
            if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                Log.d(TAG, "Camera permission GRANTED");
                // Show image chooser after permission is granted
                showImageChooser();
            } else {
                Log.w(TAG, "Camera permission DENIED");
                Toast.makeText(this, "Camera permission is required to take photos", Toast.LENGTH_LONG).show();

                // Cancel the file chooser
                if (filePathCallback != null) {
                    filePathCallback.onReceiveValue(null);
                    filePathCallback = null;
                }
            }
        } else if (requestCode == 123) {
            // Handle initial permissions
            for (int i = 0; i < permissions.length; i++) {
                Log.d(TAG, permissions[i] + ": " +
                        (grantResults[i] == PackageManager.PERMISSION_GRANTED ? "GRANTED" : "DENIED"));
            }
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);

        Log.d(TAG, "onActivityResult: request=" + requestCode +
                ", result=" + resultCode + ", data=" + (data != null ? data.getData() : "null"));

        if (requestCode == FILE_CHOOSER_RESULT_CODE) {
            if (filePathCallback == null) {
                Log.w(TAG, "filePathCallback is null, ignoring result");
                return;
            }

            Uri[] results = null;

            if (resultCode == RESULT_OK) {
                if (data == null || data.getData() == null) {
                    // Camera was used - check for the camera photo URI
                    if (cameraPhotoUri != null) {
                        // Grant read permission to the WebView
                        grantUriPermission(getPackageName(), cameraPhotoUri,
                                Intent.FLAG_GRANT_READ_URI_PERMISSION);

                        // Add to MediaStore to make it accessible
                        Intent mediaScanIntent = new Intent(Intent.ACTION_MEDIA_SCANNER_SCAN_FILE);
                        mediaScanIntent.setData(cameraPhotoUri);
                        sendBroadcast(mediaScanIntent);

                        results = new Uri[]{cameraPhotoUri};
                        Log.d(TAG, "✅ Camera photo selected: " + cameraPhotoUri);
                    } else {
                        Log.w(TAG, "Camera used but no URI available");

                        // Try to get the data from the intent if URI is null
                        if (data != null && data.getExtras() != null) {
                            // Camera might have returned bitmap in extras
                            Toast.makeText(this, "Please use gallery to select the captured image",
                                    Toast.LENGTH_LONG).show();
                        }

                        // Cancel the callback
                        filePathCallback.onReceiveValue(null);
                        filePathCallback = null;
                        return;
                    }
                } else {
                    // Gallery was used
                    Uri selectedUri = data.getData();
                    if (selectedUri != null) {
                        // Grant read permission
                        grantUriPermission(getPackageName(), selectedUri,
                                Intent.FLAG_GRANT_READ_URI_PERMISSION);

                        results = new Uri[]{selectedUri};
                        Log.d(TAG, "✅ Gallery image selected: " + selectedUri);
                    }
                }
            } else if (resultCode == RESULT_CANCELED) {
                Log.d(TAG, "User cancelled image selection");
            } else {
                Log.w(TAG, "Unknown result code: " + resultCode);
            }

            if (filePathCallback != null) {
                filePathCallback.onReceiveValue(results);
                filePathCallback = null;
            }
            cameraPhotoUri = null;
        }
    }

    private void injectDebugJavaScript() {
        String js = "javascript:" +
                "try {" +
                "   // Debug function for camera" +
                "   window.debugCamera = function() {" +
                "       console.log('=== DEBUG CAMERA ===');" +
                "       console.log('Navigator:', navigator.userAgent);" +
                "       console.log('Platform:', navigator.platform);" +
                "       console.log('MediaDevices:', !!navigator.mediaDevices);" +
                "       console.log('getUserMedia:', !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia));" +
                "" +
                "       // Test file input" +
                "       const input = document.createElement('input');" +
                "       input.type = 'file';" +
                "       input.accept = 'image/*';" +
                "       input.capture = 'environment';" +
                "" +
                "       input.onchange = function(e) {" +
                "           console.log('File selected:', e.target.files[0]);" +
                "           alert('File selected: ' + e.target.files[0].name);" +
                "       };" +
                "" +
                "       input.oncancel = function() {" +
                "           console.log('File selection cancelled');" +
                "       };" +
                "" +
                "       input.click();" +
                "   };" +
                "" +
                "   // Make it globally available" +
                "   window.addEventListener('DOMContentLoaded', function() {" +
                "       console.log('Debug functions loaded');" +
                "       if (typeof Android !== 'undefined') {" +
                "           Android.showToast('WebView ready');" +
                "       }" +
                "   });" +
                "} catch(e) {" +
                "   console.error('Error injecting debug JS:', e);" +
                "}";

        webView.evaluateJavascript(js, null);
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (backPressedCallback != null) {
            backPressedCallback.remove();
        }
    }
}
