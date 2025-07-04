class MessagesUtilities:
    """A utility class for handling and formatting standardized application messages."""
    @staticmethod
    def error_handler(error_msg, custom_content=""):
        """Generates a user-friendly title and message for a given error code.

        Args:
            error_msg (str): The internal error code or message.
            custom_content (str, optional): Additional content to include in the message. Defaults to "".

        Returns:
            tuple: A tuple containing the message title (str) and the full message body (str).
        """
        if "NotDownloadable" in error_msg:
            return (
                "Error Resolving Firmware",
                "Unable to download the selected firmware",
            )
        elif "ErrorSavingDataFiles" in error_msg:
            return (
                "Error Saving Files",
                f"An error occurred while saving data and scripts file: {custom_content}",
            )
        else:
            return ("Error", error_msg)

    @staticmethod
    def info_handler(info_msg, custom_content=""):
        """Generates a user-friendly title and message for a given information code.

        Args:
            info_msg (str): The internal information code or message.
            custom_content (str, optional): Additional content to include in the message. Defaults to "".

        Returns:
            tuple: A tuple containing the message title (str) and body (str), or (None, None) if the code is not recognized.
        """
        if  "SavedDataFiles" in info_msg:
            return ("Files successfully saved", "Data files and scripts saved successfully")
        elif "SavedPlotImage" in info_msg:
            return ("Image successfully saved", "Plot .png and .eps images saved successfully")
        else:
            return (None, None)
