class MessagesUtilities:
    @staticmethod
    def error_handler(error_msg, custom_content=""):
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
        if "SavedDataFiles" in info_msg:
            return (
                "Files successfully saved",
                "Data files and scripts saved successfully",
            )
        else:
            return (None, None)
