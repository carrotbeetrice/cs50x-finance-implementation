// Validate input
function validateInput(inputId) {
    $(inputId).children("img").show();
    $(inputId).removeClass("text-muted").addClass("text-success");
}

// Invalidate input
function invalidateInput(inputId) {
    $(inputId).children("img").hide();
    $(inputId).removeClass("text-success").addClass("text-muted");
}

// Alphanumeric validator - does not allow spaces
function alnumValidation(inputString, inputId) {
    var isalnum = inputString.match("^[a-zA-Z0-9]*$");
    if (isalnum && (inputString !== "")) {
        validateInput(inputId);
    } else {
        invalidateInput(inputId);
    }
    return isalnum;
}

// Check that password is at least 8 characters long
function checkPasswordLength(password) {
    if (password.length > 7) {
        validateInput("#length-check");
    }
    else {
        invalidateInput("#length-check");
    }

    return (password.length > 7);
}

// Bind input fields to keyup() event
$("input").on("keyup", function() {
    // Validate username input
    var usernameFieldId = "username-input";
    var usernameInputValue = document.getElementById(usernameFieldId).value;
    var usernameIsAlnum = alnumValidation(usernameInputValue, "#username-check");

    // Validate password input
    var passwordFieldId = "password-input";
    var passwordInputValue = document.getElementById(passwordFieldId).value;

    var isMinLength = checkPasswordLength(passwordInputValue);
    var passwordIsAlnum = alnumValidation(passwordInputValue, "#alnum-check");

    // Enable 'Register' button if all validation criteria has been met
    if (usernameIsAlnum && isMinLength && passwordIsAlnum) {
        $("#register-btn").prop("disabled", false);
    }
});